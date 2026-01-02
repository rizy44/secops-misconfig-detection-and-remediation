"""
Auto-Fix Engine
================
Automatically fixes IaC security misconfigurations based on runbook catalog.
"""

import os
import re
import copy
import logging
import hashlib
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import yaml

from .scanner import Finding, Severity

logger = logging.getLogger(__name__)


class FixType(Enum):
    REGEX_REPLACE = "regex_replace"
    YAML_TRANSFORM = "yaml_transform"
    AST_TRANSFORM = "ast_transform"
    FILE_INJECT = "file_inject"
    YAML_FORMAT = "yaml_format"
    YAML_INJECT = "yaml_inject"


class FixStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    REQUIRES_APPROVAL = "requires_approval"


@dataclass
class FixAction:
    """Represents a single fix action."""
    id: str
    runbook_id: str
    finding: Finding
    fix_type: FixType
    target_file: str
    original_content: str
    fixed_content: str
    status: FixStatus = FixStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    diff: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "runbook_id": self.runbook_id,
            "finding_id": self.finding.id,
            "fix_type": self.fix_type.value,
            "target_file": self.target_file,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "diff": self.diff,
        }


@dataclass
class FixBatch:
    """Represents a batch of fix actions."""
    id: str
    target_path: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    status: str = "pending"  # pending, running, completed, failed
    actions: List[FixAction] = field(default_factory=list)
    backup_path: Optional[str] = None
    
    @property
    def total_actions(self) -> int:
        return len(self.actions)
    
    @property
    def successful_actions(self) -> int:
        return len([a for a in self.actions if a.status == FixStatus.SUCCESS])
    
    @property
    def failed_actions(self) -> int:
        return len([a for a in self.actions if a.status == FixStatus.FAILED])
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "target_path": self.target_path,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "total_actions": self.total_actions,
            "successful_actions": self.successful_actions,
            "failed_actions": self.failed_actions,
            "actions": [a.to_dict() for a in self.actions],
            "backup_path": self.backup_path,
        }


@dataclass
class Runbook:
    """Represents a fix runbook from catalog."""
    id: str
    name: str
    description: str
    finding_patterns: List[Dict]
    fix: Dict
    variables_required: List[Dict] = field(default_factory=list)
    verify: List[Dict] = field(default_factory=list)
    severity: str = "MEDIUM"
    auto_approve: bool = False


class RunbookCatalog:
    """Manages fix runbooks."""
    
    def __init__(self, catalog_path: Path):
        self.catalog_path = catalog_path
        self.runbooks: Dict[str, Runbook] = {}
        self._load_catalog()
    
    def _load_catalog(self):
        """Load runbooks from YAML catalog."""
        if not self.catalog_path.exists():
            logger.warning(f"Runbook catalog not found: {self.catalog_path}")
            return
        
        with open(self.catalog_path, 'r') as f:
            data = yaml.safe_load(f)
        
        for runbook_id, runbook_data in data.items():
            runbook = Runbook(
                id=runbook_id,
                name=runbook_data.get("name", runbook_id),
                description=runbook_data.get("description", ""),
                finding_patterns=runbook_data.get("finding_patterns", []),
                fix=runbook_data.get("fix", {}),
                variables_required=runbook_data.get("variables_required", []),
                verify=runbook_data.get("verify", []),
                severity=runbook_data.get("severity", "MEDIUM"),
                auto_approve=runbook_data.get("auto_approve", False),
            )
            self.runbooks[runbook_id] = runbook
        
        logger.info(f"Loaded {len(self.runbooks)} runbooks from catalog")
    
    def find_runbook(self, finding: Finding) -> Optional[Runbook]:
        """Find matching runbook for a finding."""
        for runbook in self.runbooks.values():
            for pattern in runbook.finding_patterns:
                # Match by scanner and check_id
                scanner_pattern = pattern.get(finding.scanner, "")
                if scanner_pattern and scanner_pattern == finding.check_id:
                    return runbook
                
                # Match by regex on title/description
                regex_pattern = pattern.get("regex", "")
                if regex_pattern:
                    if re.search(regex_pattern, finding.title, re.IGNORECASE):
                        return runbook
                    if re.search(regex_pattern, finding.description, re.IGNORECASE):
                        return runbook
        
        return None
    
    def get_runbook(self, runbook_id: str) -> Optional[Runbook]:
        """Get runbook by ID."""
        return self.runbooks.get(runbook_id)


class AutoFixer:
    """
    Auto-Fix Engine for IaC security misconfigurations.
    """
    
    def __init__(self, config: Dict = None, catalog_path: Path = None):
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.max_attempts = self.config.get("max_attempts", 3)
        self.require_approval = self.config.get("require_approval", [])
        self.auto_approve = self.config.get("auto_approve", [])
        
        # Load runbook catalog
        if catalog_path:
            self.catalog = RunbookCatalog(catalog_path)
        else:
            catalog_file = self.config.get("runbook_catalog", "/app/runbooks/catalog.yml")
            self.catalog = RunbookCatalog(Path(catalog_file))
        
        # Variables for substitution
        self.variables: Dict[str, str] = {}
        
        # Fix history
        self._fix_history: List[FixBatch] = []
        self._action_counter = 0
    
    def set_variables(self, variables: Dict[str, str]):
        """Set variables for runbook substitution."""
        self.variables.update(variables)
    
    def analyze(self, findings: List[Finding], target_path: Path) -> List[Tuple[Finding, Runbook]]:
        """
        Analyze findings and find matching runbooks.
        
        Returns:
            List of (finding, runbook) tuples for fixable findings
        """
        fixable = []
        
        for finding in findings:
            runbook = self.catalog.find_runbook(finding)
            if runbook:
                fixable.append((finding, runbook))
                logger.info(f"Found runbook '{runbook.name}' for finding: {finding.title}")
            else:
                logger.debug(f"No runbook found for finding: {finding.title}")
        
        return fixable
    
    def fix(self, findings: List[Finding], target_path: Path) -> FixBatch:
        """
        Apply fixes for all findings that have matching runbooks.
        
        Args:
            findings: List of security findings
            target_path: Path to the files to fix
        
        Returns:
            FixBatch with all fix actions and their results
        """
        batch_id = f"fix_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        batch = FixBatch(
            id=batch_id,
            target_path=str(target_path),
            created_at=datetime.now()
        )
        
        if not self.enabled:
            logger.info("Auto-fix is disabled")
            batch.status = "skipped"
            return batch
        
        # Create backup
        backup_path = self._create_backup(target_path)
        batch.backup_path = str(backup_path)
        
        batch.status = "running"
        
        # Analyze and get fixable findings
        fixable = self.analyze(findings, target_path)
        
        for finding, runbook in fixable:
            action = self._apply_fix(finding, runbook, target_path)
            batch.actions.append(action)
        
        batch.completed_at = datetime.now()
        batch.status = "completed" if batch.failed_actions == 0 else "failed"
        
        self._fix_history.append(batch)
        
        logger.info(f"Fix batch completed: {batch.successful_actions}/{batch.total_actions} successful")
        
        return batch
    
    def _apply_fix(self, finding: Finding, runbook: Runbook, target_path: Path) -> FixAction:
        """Apply a single fix based on runbook."""
        self._action_counter += 1
        action_id = f"action_{self._action_counter}"
        
        fix_type_str = runbook.fix.get("type", "regex_replace")
        fix_type = FixType(fix_type_str)
        
        # Find target file
        target_file = self._find_target_file(finding, runbook, target_path)
        
        action = FixAction(
            id=action_id,
            runbook_id=runbook.id,
            finding=finding,
            fix_type=fix_type,
            target_file=str(target_file) if target_file else "",
            original_content="",
            fixed_content="",
        )
        
        # Check approval requirements
        if not runbook.auto_approve and runbook.severity in ["HIGH", "CRITICAL"]:
            if any(cat in runbook.id for cat in self.require_approval):
                action.status = FixStatus.REQUIRES_APPROVAL
                return action
        
        action.started_at = datetime.now()
        
        try:
            if not target_file or not target_file.exists():
                action.status = FixStatus.FAILED
                action.error_message = f"Target file not found: {finding.file_path}"
                action.completed_at = datetime.now()
                return action
            
            # Read original content
            original_content = target_file.read_text()
            action.original_content = original_content
            
            # Apply fix based on type
            if fix_type == FixType.REGEX_REPLACE:
                fixed_content = self._apply_regex_fix(original_content, runbook)
            elif fix_type == FixType.YAML_TRANSFORM:
                fixed_content = self._apply_yaml_transform(original_content, runbook)
            elif fix_type == FixType.YAML_FORMAT:
                fixed_content = self._apply_yaml_format(original_content, runbook)
            else:
                action.status = FixStatus.SKIPPED
                action.error_message = f"Unsupported fix type: {fix_type}"
                action.completed_at = datetime.now()
                return action
            
            action.fixed_content = fixed_content
            
            # Generate diff
            action.diff = self._generate_diff(original_content, fixed_content)
            
            # Write fixed content
            if fixed_content != original_content:
                target_file.write_text(fixed_content)
                action.status = FixStatus.SUCCESS
                logger.info(f"Applied fix: {runbook.name} to {target_file}")
            else:
                action.status = FixStatus.SKIPPED
                action.error_message = "No changes needed"
            
        except Exception as e:
            action.status = FixStatus.FAILED
            action.error_message = str(e)
            logger.error(f"Failed to apply fix: {e}")
        
        action.completed_at = datetime.now()
        return action
    
    def _find_target_file(self, finding: Finding, runbook: Runbook, target_path: Path) -> Optional[Path]:
        """Find the target file to fix."""
        # First try the finding's file path
        if finding.file_path:
            file_path = target_path / finding.file_path
            if file_path.exists():
                return file_path
            
            # Try just the filename
            for pattern in runbook.fix.get("target_files", ["*"]):
                for f in target_path.glob(f"**/{pattern}"):
                    if f.name == Path(finding.file_path).name:
                        return f
        
        # Search using runbook target patterns
        for pattern in runbook.fix.get("target_files", []):
            matches = list(target_path.glob(f"**/{pattern}"))
            if matches:
                return matches[0]
        
        return None
    
    def _apply_regex_fix(self, content: str, runbook: Runbook) -> str:
        """Apply regex-based fix."""
        fixed = content
        
        rules = runbook.fix.get("rules", [])
        for rule in rules:
            pattern = rule.get("pattern", "")
            replacement = rule.get("replacement", "")
            
            # Substitute variables
            replacement = self._substitute_variables(replacement)
            
            if pattern:
                fixed = re.sub(pattern, replacement, fixed, flags=re.MULTILINE | re.DOTALL)
        
        return fixed
    
    def _apply_yaml_transform(self, content: str, runbook: Runbook) -> str:
        """Apply YAML transformation fix."""
        try:
            data = yaml.safe_load(content)
            if data is None:
                return content
            
            rules = runbook.fix.get("rules", [])
            for rule in rules:
                data = self._apply_yaml_rule(data, rule)
            
            return yaml.dump(data, default_flow_style=False, sort_keys=False)
        except yaml.YAMLError as e:
            logger.error(f"YAML parse error: {e}")
            return content
    
    def _apply_yaml_rule(self, data: Any, rule: Dict) -> Any:
        """Apply a single YAML transformation rule."""
        path = rule.get("path", "")
        when = rule.get("when", {})
        when_missing = rule.get("when_missing", "")
        add = rule.get("add", {})
        ensure = rule.get("ensure", {})
        set_value = rule.get("set", {})
        
        if isinstance(data, dict):
            # Check conditions
            if when:
                matches = all(data.get(k) == v for k, v in when.items() if v != "*")
                if not matches:
                    return data
            
            if when_missing and when_missing in data:
                return data
            
            # Apply modifications
            if add:
                for k, v in add.items():
                    if k not in data:
                        data[k] = self._substitute_variables(v) if isinstance(v, str) else v
            
            if ensure:
                data.update({k: self._substitute_variables(v) if isinstance(v, str) else v 
                           for k, v in ensure.items()})
            
            if set_value:
                data.update({k: self._substitute_variables(v) if isinstance(v, str) else v 
                           for k, v in set_value.items()})
        
        elif isinstance(data, list):
            data = [self._apply_yaml_rule(item, rule) for item in data]
        
        return data
    
    def _apply_yaml_format(self, content: str, runbook: Runbook) -> str:
        """Apply YAML formatting fixes."""
        rules = runbook.fix.get("rules", [{}])[0]
        
        # Remove trailing spaces
        if rules.get("remove_trailing_spaces", True):
            content = "\n".join(line.rstrip() for line in content.split("\n"))
        
        # Ensure final newline
        if rules.get("ensure_final_newline", True):
            if not content.endswith("\n"):
                content += "\n"
        
        return content
    
    def _substitute_variables(self, text: str) -> str:
        """Substitute variables in text."""
        if not isinstance(text, str):
            return text
        
        result = text
        for var_name, var_value in self.variables.items():
            result = result.replace(f"${{{var_name}}}", var_value)
            result = result.replace(f"${{var.{var_name}}}", var_value)
        
        return result
    
    def _create_backup(self, target_path: Path) -> Path:
        """Create backup of target directory."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = target_path.parent / f"{target_path.name}_backup_{timestamp}"
        
        shutil.copytree(target_path, backup_path)
        logger.info(f"Created backup: {backup_path}")
        
        return backup_path
    
    def _generate_diff(self, original: str, fixed: str) -> str:
        """Generate simple diff between original and fixed content."""
        import difflib
        
        original_lines = original.splitlines(keepends=True)
        fixed_lines = fixed.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            original_lines, fixed_lines,
            fromfile="original",
            tofile="fixed"
        )
        
        return "".join(diff)
    
    def rollback(self, batch_id: str) -> bool:
        """Rollback a fix batch using backup."""
        batch = next((b for b in self._fix_history if b.id == batch_id), None)
        if not batch:
            logger.error(f"Fix batch not found: {batch_id}")
            return False
        
        if not batch.backup_path:
            logger.error(f"No backup available for batch: {batch_id}")
            return False
        
        backup_path = Path(batch.backup_path)
        if not backup_path.exists():
            logger.error(f"Backup not found: {backup_path}")
            return False
        
        target_path = Path(batch.target_path)
        
        # Remove current and restore backup
        shutil.rmtree(target_path)
        shutil.copytree(backup_path, target_path)
        
        logger.info(f"Rolled back batch {batch_id}")
        return True
    
    def get_history(self) -> List[FixBatch]:
        """Get fix history."""
        return self._fix_history.copy()
    
    def verify_fixes(self, batch: FixBatch) -> Dict[str, bool]:
        """Verify that fixes were applied correctly."""
        results = {}
        
        for action in batch.actions:
            if action.status != FixStatus.SUCCESS:
                results[action.id] = False
                continue
            
            runbook = self.catalog.get_runbook(action.runbook_id)
            if not runbook or not runbook.verify:
                results[action.id] = True
                continue
            
            # Verify each condition
            target_file = Path(action.target_file)
            if not target_file.exists():
                results[action.id] = False
                continue
            
            content = target_file.read_text()
            verified = True
            
            for verify in runbook.verify:
                verify_type = verify.get("type", "")
                
                if verify_type == "regex_not_match":
                    pattern = verify.get("pattern", "")
                    if re.search(pattern, content):
                        verified = False
                        break
                
                elif verify_type == "regex_match":
                    pattern = verify.get("pattern", "")
                    if not re.search(pattern, content):
                        verified = False
                        break
            
            results[action.id] = verified
        
        return results


def create_fixer_from_config(config_path: str) -> AutoFixer:
    """Create AutoFixer from YAML config file."""
    with open(config_path, 'r') as f:
        config_data = yaml.safe_load(f)
    
    fix_config = config_data.get('auto_fix', {})
    catalog_path = Path(fix_config.get('runbook_catalog', '/app/runbooks/catalog.yml'))
    
    return AutoFixer(fix_config, catalog_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test the fixer
    catalog_path = Path("./runbooks/catalog.yml")
    
    if catalog_path.exists():
        fixer = AutoFixer(
            config={"enabled": True},
            catalog_path=catalog_path
        )
        
        fixer.set_variables({
            "admin_cidr": "10.0.0.0/8",
            "internal_cidr": "10.10.50.0/24"
        })
        
        print(f"Loaded {len(fixer.catalog.runbooks)} runbooks")
        for rb_id, rb in fixer.catalog.runbooks.items():
            print(f"  - {rb_id}: {rb.name}")
