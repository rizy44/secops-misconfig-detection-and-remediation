# Pre-Push Security Checklist

**Run this checklist before pushing to GitHub to ensure no sensitive data is committed.**

## ✅ Quick Verification

```bash
# Initialize git repository (if not already done)
git init
git add .gitignore .gitattributes

# Check what will be committed
git status

# Verify no sensitive files are tracked
git ls-files | grep -E "openrc|tfstate|tfvars|\.env|\.key|\.pem|inventory\.ini$"
# ⚠️ This should return EMPTY. If it shows files, they need to be removed!
```

## 🔍 Detailed Checks

### 1. Verify .gitignore is working

```bash
# Check ignored files
git status --ignored

# Should show these as ignored:
# - terraform/terraform.tfstate
# - terraform/terraform.tfstate.backup
# - terraform/terraform.tfvars
# - ansible/files/tenantA-openrc.sh
# - ansible/inventory.ini
```

### 2. Check for credentials in code

```bash
# Search for passwords
git grep -i "password.*=" | grep -v "PASSWORD.*=" | grep -v ".example"

# Search for API keys
git grep -E "sk-[a-zA-Z0-9]{32,}"
git grep -i "api_key.*="

# Search for hardcoded IPs (in code, not docs)
git grep -E "[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}" -- "*.py" "*.sh" | grep -v ".example"
```

### 3. Verify example files exist

```bash
ls -la ansible/files/*.example
ls -la terraform/*.example
ls -la ansible/*.example

# Should see:
# - ansible/files/tenantA-openrc.sh.example
# - terraform/terraform.tfvars.example
# - ansible/inventory.ini.example
```

### 4. Check file permissions

```bash
# Ensure sensitive files are not world-readable (if they exist locally)
test -f ansible/files/tenantA-openrc.sh && ls -l ansible/files/tenantA-openrc.sh
test -f terraform/terraform.tfvars && ls -l terraform/terraform.tfvars
```

## 🚫 Files That Should NOT Be Tracked

The following files should be in .gitignore and NOT appear in `git ls-files`:

- `terraform/terraform.tfstate`
- `terraform/terraform.tfstate.backup`
- `terraform/terraform.tfvars`
- `ansible/inventory.ini`
- `ansible/files/tenantA-openrc.sh`
- `*.env`
- `*.key`
- `*.pem`
- `*.db`
- `*.log`

## ✅ Files That SHOULD Be Tracked

These example files should be committed:

- `.gitignore`
- `.gitattributes`
- `SETUP.md`
- `README.md`
- `ansible/files/tenantA-openrc.sh.example`
- `terraform/terraform.tfvars.example`
- `ansible/inventory.ini.example`
- All `.tf` files
- All `.yml` files
- All `.py` files
- Documentation files

## 🔧 Fix If Files Are Accidentally Tracked

If sensitive files are already being tracked:

```bash
# Remove from git tracking (but keep local file)
git rm --cached terraform/terraform.tfstate
git rm --cached terraform/terraform.tfvars
git rm --cached ansible/files/tenantA-openrc.sh
git rm --cached ansible/inventory.ini

# Commit the removal
git commit -m "Remove sensitive files from tracking"
```

## 📝 Ready to Push Checklist

Before running `git push`, verify:

- [ ] `.gitignore` is committed
- [ ] All `.example` files are committed
- [ ] `SETUP.md` exists and is complete
- [ ] `README.md` has setup instructions
- [ ] No credentials in `git log -p` (check recent commits)
- [ ] `terraform.tfstate` is NOT tracked
- [ ] `terraform.tfvars` is NOT tracked
- [ ] `*-openrc.sh` is NOT tracked (except .example)
- [ ] `inventory.ini` is NOT tracked (except .example)
- [ ] No hardcoded passwords in code
- [ ] No API keys in code
- [ ] Documentation doesn't contain real credentials

## 🚀 Safe to Push

If all checks pass:

```bash
# First commit (if new repo)
git add .
git commit -m "Initial commit: SecOps SOAR platform

- Security automation for OpenStack
- Terraform + Ansible deployment
- AI-powered remediation suggestions
- Full observability stack
- Documentation and examples"

# Add remote and push
git remote add origin <your-repo-url>
git branch -M main
git push -u origin main
```

## 🔒 Post-Push Verification

After pushing, verify on GitHub:

```bash
# Check remote repository
# Go to: https://github.com/<your-username>/<your-repo>

# Verify these files are NOT visible:
# - terraform.tfstate
# - terraform.tfvars (should see .example instead)
# - tenantA-openrc.sh (should see .example instead)
# - inventory.ini (should see .example instead)
```

## ⚠️ If You Accidentally Pushed Secrets

If you accidentally pushed credentials:

1. **Immediately rotate all credentials**:
   - Change OpenStack password
   - Regenerate API keys
   - Update SSH keys

2. **Remove from git history**:
   ```bash
   # Use BFG Repo Cleaner or git filter-branch
   # See: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository
   ```

3. **Force push cleaned history**:
   ```bash
   git push --force
   ```

## 📞 Need Help?

- Review [SETUP.md](SETUP.md) for configuration guidance
- Check GitHub's [Removing sensitive data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
- Use [git-secrets](https://github.com/awslabs/git-secrets) tool for automated scanning

---

**Remember**: Once secrets are pushed to a public repository, they should be considered compromised. Always verify before pushing!

