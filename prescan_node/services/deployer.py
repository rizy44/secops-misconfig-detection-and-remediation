"""
Deployer Service
=================
Handles deployment of validated Terraform and Ansible configurations.
"""

import os
import logging
import subprocess
import threading
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import yaml

logger = logging.getLogger(__name__)


class DeploymentStatus(Enum):
    PENDING = "pending"
    PLANNING = "planning"
    PLAN_READY = "plan_ready"
    APPLYING = "applying"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLBACK = "rollback"


@dataclass
class TerraformPlan:
    """Represents a Terraform plan."""
    plan_file: str
    resources_to_add: int = 0
    resources_to_change: int = 0
    resources_to_destroy: int = 0
    plan_output: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "plan_file": self.plan_file,
            "resources_to_add": self.resources_to_add,
            "resources_to_change": self.resources_to_change,
            "resources_to_destroy": self.resources_to_destroy,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class AnsibleRun:
    """Represents an Ansible playbook run."""
    playbook: str
    inventory: str
    status: str = "pending"
    output: str = ""
    changed_tasks: int = 0
    failed_tasks: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        return {
            "playbook": self.playbook,
            "inventory": self.inventory,
            "status": self.status,
            "changed_tasks": self.changed_tasks,
            "failed_tasks": self.failed_tasks,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class Deployment:
    """Represents a complete deployment."""
    id: str
    source_path: str
    output_path: str
    status: DeploymentStatus = DeploymentStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    terraform_plan: Optional[TerraformPlan] = None
    ansible_runs: List[AnsibleRun] = field(default_factory=list)
    error_message: Optional[str] = None
    
    @property
    def duration_seconds(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "source_path": self.source_path,
            "output_path": self.output_path,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "terraform_plan": self.terraform_plan.to_dict() if self.terraform_plan else None,
            "ansible_runs": [r.to_dict() for r in self.ansible_runs],
            "error_message": self.error_message,
        }


class TerraformDeployer:
    """Handles Terraform deployments."""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.auto_apply = self.config.get("auto_apply", False)
        self.plan_only = self.config.get("plan_only", True)
        self.backend_config = self.config.get("backend_config", {})
    
    def init(self, working_dir: Path) -> tuple:
        """Initialize Terraform in the working directory."""
        cmd = ["terraform", "init", "-no-color"]
        
        # Add backend config
        for key, value in self.backend_config.items():
            cmd.extend([f"-backend-config={key}={value}"])
        
        return self._run_command(cmd, working_dir)
    
    def plan(self, working_dir: Path, plan_file: str = "tfplan") -> TerraformPlan:
        """Create a Terraform plan."""
        plan_path = working_dir / plan_file
        
        cmd = [
            "terraform", "plan",
            "-no-color",
            "-out", str(plan_path),
            "-detailed-exitcode"
        ]
        
        exit_code, stdout, stderr = self._run_command(cmd, working_dir)
        
        plan = TerraformPlan(
            plan_file=str(plan_path),
            plan_output=stdout
        )
        
        # Parse plan output for resource counts
        plan.resources_to_add = stdout.count("# (to add)")
        plan.resources_to_change = stdout.count("# (to change)")
        plan.resources_to_destroy = stdout.count("# (to destroy)")
        
        # Check exit code
        # 0 = no changes, 1 = error, 2 = changes
        if exit_code == 1:
            raise Exception(f"Terraform plan failed: {stderr}")
        
        return plan
    
    def apply(self, working_dir: Path, plan_file: str = "tfplan") -> tuple:
        """Apply a Terraform plan."""
        plan_path = working_dir / plan_file
        
        if not plan_path.exists():
            raise Exception(f"Plan file not found: {plan_path}")
        
        cmd = [
            "terraform", "apply",
            "-no-color",
            "-auto-approve",
            str(plan_path)
        ]
        
        return self._run_command(cmd, working_dir)
    
    def destroy(self, working_dir: Path) -> tuple:
        """Destroy Terraform resources."""
        cmd = [
            "terraform", "destroy",
            "-no-color",
            "-auto-approve"
        ]
        
        return self._run_command(cmd, working_dir)
    
    def output(self, working_dir: Path) -> Dict:
        """Get Terraform outputs."""
        cmd = ["terraform", "output", "-json"]
        exit_code, stdout, stderr = self._run_command(cmd, working_dir)
        
        if exit_code != 0:
            return {}
        
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return {}
    
    def validate(self, working_dir: Path) -> tuple:
        """Validate Terraform configuration."""
        cmd = ["terraform", "validate", "-json"]
        return self._run_command(cmd, working_dir)
    
    @staticmethod
    def _run_command(cmd: List[str], cwd: Path) -> tuple:
        """Run a command and return (exit_code, stdout, stderr)."""
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=600
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except Exception as e:
            return -1, "", str(e)


class AnsibleDeployer:
    """Handles Ansible deployments."""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.inventory = self.config.get("inventory", "/etc/ansible/hosts")
        self.private_key = self.config.get("private_key", None)
        self.become = self.config.get("become", True)
        self.extra_vars = self.config.get("extra_vars", {})
    
    def run_playbook(self, playbook_path: Path, inventory: str = None) -> AnsibleRun:
        """Run an Ansible playbook."""
        inventory = inventory or self.inventory
        
        run = AnsibleRun(
            playbook=str(playbook_path),
            inventory=inventory,
            started_at=datetime.now()
        )
        
        cmd = [
            "ansible-playbook",
            str(playbook_path),
            "-i", inventory,
        ]
        
        if self.become:
            cmd.append("--become")
        
        if self.private_key:
            cmd.extend(["--private-key", self.private_key])
        
        # Add extra vars
        for key, value in self.extra_vars.items():
            cmd.extend(["-e", f"{key}={value}"])
        
        exit_code, stdout, stderr = self._run_command(cmd)
        
        run.output = stdout + stderr
        run.completed_at = datetime.now()
        
        if exit_code == 0:
            run.status = "success"
        else:
            run.status = "failed"
        
        # Parse output for task counts
        run.changed_tasks = stdout.count("changed=")
        run.failed_tasks = stdout.count("failed=1")
        
        return run
    
    def check_syntax(self, playbook_path: Path) -> tuple:
        """Check playbook syntax."""
        cmd = [
            "ansible-playbook",
            str(playbook_path),
            "--syntax-check"
        ]
        
        return self._run_command(cmd)
    
    def list_tasks(self, playbook_path: Path) -> List[str]:
        """List tasks in a playbook."""
        cmd = [
            "ansible-playbook",
            str(playbook_path),
            "--list-tasks"
        ]
        
        exit_code, stdout, _ = self._run_command(cmd)
        
        if exit_code != 0:
            return []
        
        tasks = []
        for line in stdout.split("\n"):
            if "TASK:" in line or "task:" in line.lower():
                tasks.append(line.strip())
        
        return tasks
    
    @staticmethod
    def _run_command(cmd: List[str]) -> tuple:
        """Run a command and return (exit_code, stdout, stderr)."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except Exception as e:
            return -1, "", str(e)


class Deployer:
    """
    Main deployment orchestrator.
    Handles both Terraform and Ansible deployments.
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.output_dir = Path(self.config.get("output_dir", "/deploy/out"))
        
        # Initialize deployers
        tf_config = self.config.get("terraform", {})
        ansible_config = self.config.get("ansible", {})
        
        self.terraform = TerraformDeployer(tf_config)
        self.ansible = AnsibleDeployer(ansible_config)
        
        # Deployment history
        self._deployments: Dict[str, Deployment] = {}
        self._deployment_counter = 0
        
        # Verification settings
        self.verify_enabled = self.config.get("verify", {}).get("enabled", True)
        self.verify_timeout = self.config.get("verify", {}).get("timeout", 300)
    
    def deploy(self, source_path: Path, deploy_terraform: bool = True, 
               deploy_ansible: bool = True) -> Deployment:
        """
        Execute a full deployment.
        
        Args:
            source_path: Path to the deployment files
            deploy_terraform: Whether to deploy Terraform
            deploy_ansible: Whether to deploy Ansible
        
        Returns:
            Deployment object with status and results
        """
        self._deployment_counter += 1
        deploy_id = f"deploy_{datetime.now().strftime('%Y%m%d%H%M%S')}_{self._deployment_counter}"
        
        deployment = Deployment(
            id=deploy_id,
            source_path=str(source_path),
            output_path=str(self.output_dir / deploy_id)
        )
        self._deployments[deploy_id] = deployment
        
        if not self.enabled:
            logger.info("Deployer is disabled")
            deployment.status = DeploymentStatus.CANCELLED
            return deployment
        
        deployment.started_at = datetime.now()
        
        try:
            # Find Terraform files
            tf_files = list(source_path.glob("**/*.tf"))
            
            # Find Ansible playbooks
            playbooks = list(source_path.glob("**/playbook*.yml")) + \
                       list(source_path.glob("**/*-playbook.yml"))
            
            # Deploy Terraform first
            if deploy_terraform and tf_files:
                deployment.status = DeploymentStatus.PLANNING
                tf_dir = tf_files[0].parent
                
                # Initialize
                logger.info("Initializing Terraform...")
                exit_code, stdout, stderr = self.terraform.init(tf_dir)
                if exit_code != 0:
                    raise Exception(f"Terraform init failed: {stderr}")
                
                # Validate
                logger.info("Validating Terraform configuration...")
                exit_code, stdout, stderr = self.terraform.validate(tf_dir)
                if exit_code != 0:
                    raise Exception(f"Terraform validation failed: {stderr}")
                
                # Plan
                logger.info("Creating Terraform plan...")
                plan = self.terraform.plan(tf_dir)
                deployment.terraform_plan = plan
                deployment.status = DeploymentStatus.PLAN_READY
                
                # Apply (if auto_apply is enabled)
                if self.terraform.auto_apply:
                    deployment.status = DeploymentStatus.APPLYING
                    logger.info("Applying Terraform plan...")
                    exit_code, stdout, stderr = self.terraform.apply(tf_dir)
                    if exit_code != 0:
                        raise Exception(f"Terraform apply failed: {stderr}")
            
            # Deploy Ansible
            if deploy_ansible and playbooks:
                deployment.status = DeploymentStatus.APPLYING
                
                for playbook in playbooks:
                    logger.info(f"Running playbook: {playbook.name}")
                    
                    # Check syntax first
                    exit_code, _, stderr = self.ansible.check_syntax(playbook)
                    if exit_code != 0:
                        logger.warning(f"Playbook syntax check failed: {stderr}")
                        continue
                    
                    # Run playbook
                    run = self.ansible.run_playbook(playbook)
                    deployment.ansible_runs.append(run)
                    
                    if run.status == "failed":
                        logger.error(f"Playbook failed: {playbook.name}")
            
            # Check final status
            failed_runs = [r for r in deployment.ansible_runs if r.status == "failed"]
            if failed_runs:
                deployment.status = DeploymentStatus.FAILED
                deployment.error_message = f"{len(failed_runs)} playbook(s) failed"
            else:
                deployment.status = DeploymentStatus.SUCCESS
            
            # Verify deployment (if enabled)
            if self.verify_enabled and deployment.status == DeploymentStatus.SUCCESS:
                self._verify_deployment(deployment)
                
        except Exception as e:
            deployment.status = DeploymentStatus.FAILED
            deployment.error_message = str(e)
            logger.error(f"Deployment failed: {e}")
        
        deployment.completed_at = datetime.now()
        
        logger.info(f"Deployment {deploy_id} completed with status: {deployment.status.value}")
        
        return deployment
    
    def _verify_deployment(self, deployment: Deployment):
        """Verify that deployment was successful."""
        logger.info("Verifying deployment...")
        
        # Get Terraform outputs
        if deployment.terraform_plan:
            tf_dir = Path(deployment.source_path) / "terraform"
            if tf_dir.exists():
                outputs = self.terraform.output(tf_dir)
                logger.info(f"Terraform outputs: {outputs}")
        
        # TODO: Add more verification logic
        # - Check Ansible host connectivity
        # - Verify services are running
        # - Run smoke tests
    
    def get_deployment(self, deploy_id: str) -> Optional[Deployment]:
        """Get deployment by ID."""
        return self._deployments.get(deploy_id)
    
    def list_deployments(self) -> List[Deployment]:
        """List all deployments."""
        return list(self._deployments.values())
    
    def cancel_deployment(self, deploy_id: str) -> bool:
        """Cancel a pending deployment."""
        deployment = self._deployments.get(deploy_id)
        if not deployment:
            return False
        
        if deployment.status in [DeploymentStatus.PENDING, DeploymentStatus.PLAN_READY]:
            deployment.status = DeploymentStatus.CANCELLED
            deployment.completed_at = datetime.now()
            return True
        
        return False
    
    def rollback_deployment(self, deploy_id: str) -> bool:
        """Rollback a deployment (Terraform destroy)."""
        deployment = self._deployments.get(deploy_id)
        if not deployment:
            return False
        
        if deployment.terraform_plan:
            tf_dir = Path(deployment.source_path)
            
            # Find terraform directory
            tf_files = list(tf_dir.glob("**/*.tf"))
            if tf_files:
                tf_dir = tf_files[0].parent
                
                deployment.status = DeploymentStatus.ROLLBACK
                exit_code, stdout, stderr = self.terraform.destroy(tf_dir)
                
                if exit_code == 0:
                    deployment.status = DeploymentStatus.CANCELLED
                    deployment.completed_at = datetime.now()
                    return True
                else:
                    deployment.error_message = f"Rollback failed: {stderr}"
        
        return False


def create_deployer_from_config(config_path: str) -> Deployer:
    """Create Deployer from YAML config file."""
    with open(config_path, 'r') as f:
        config_data = yaml.safe_load(f)
    
    deploy_config = config_data.get('deploy', {})
    return Deployer(deploy_config)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    deployer = Deployer({
        "enabled": True,
        "terraform": {
            "auto_apply": False,
            "plan_only": True
        },
        "ansible": {
            "become": True
        }
    })
    
    print("Deployer initialized")
    print(f"  Terraform auto_apply: {deployer.terraform.auto_apply}")
    print(f"  Ansible become: {deployer.ansible.become}")
