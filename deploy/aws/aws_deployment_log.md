# AWS Deployment Execution Log — Telex
**Target Hackathon**: AWS Hackathon 2026  
**Deployment Date**: 2026-10-01  
**Target Region**: `us-east-1`  
**Project Tag**: `Project=telex`  
**Deployer**: Antigravity AI Coding Agent  

---

## 1. Verified Architecture & Cost Guardrails
- **Compute**: 1x EC2 `t3.small` (Ubuntu 24.04 LTS, 20 GB gp3) — ~$15.00/mo
- **Database**: 1x RDS PostgreSQL `db.t4g.micro` (Single-AZ, 20 GB gp3, private) — ~$13.00/mo
- **Networking**: 1x Elastic IP (`184-194-145-93.sslip.io`) — ~$3.60/mo
- **Security**: Ingress restricted; RDS allows port 5432 only from EC2 Security Group.
- **Excluded**: No NAT Gateway, no Application Load Balancer, no Multi-AZ.
- **Estimated Total**: ~$32 - $35/month.

---

## 2. Resource Inventory & Credentials Map

| Resource | Identifier / ID | Status | Endpoint / IP |
|---|---|---|---|
| **Key Pair** | `telex-key` | Created | `telex-key.pem` (Local secure) |
| **EC2 Security Group** | `sg-0c2072740d2612046` | Active | Ports 80, 443 (0.0.0.0/0), 22 (SSH) |
| **RDS Security Group** | `sg-0d3bdcde4c846de6b` | Active | Port 5432 (from `sg-0c2072740d2612046` only) |
| **RDS Subnet Group** | `telex-rds-subnets` | Active | `subnet-062f972ddbae44225`, `subnet-07c124ce3603a1590` |
| **RDS PostgreSQL** | `telex-db` (`db.t4g.micro`) | `available` | `telex-db.ck5ukoc6mf86.us-east-1.rds.amazonaws.com:5432` |
| **SSM Secret Parameter** | `/telex/production/db_password` | Standard (Free) | SecureString (AES-256) |
| **EC2 Instance** | `i-00c45f6bc03841d7a` (`t3.small`) | `running` | `184.194.145.93` |
| **Elastic IP** | `eipalloc-05b2465eba59f43a2` | Associated | `184.194.145.93` |
| **API Domain** | `184-194-145-93.sslip.io` | Active | Auto-SSL via Caddy |

---

## 3. CLI Execution History & Submission Proof

```bash
# 1. Created Key Pair
aws ec2 create-key-pair \
  --key-name telex-key \
  --key-type rsa \
  --key-format pem \
  --tag-specifications "ResourceType=key-pair,Tags=[{Key=Project,Value=telex}]" \
  --region us-east-1

# 2. Created EC2 Security Group
aws ec2 create-security-group \
  --group-name telex-ec2-sg \
  --description "Telex EC2 Web and API Security Group" \
  --vpc-id vpc-0aeec9ca9d2a97c26 \
  --tag-specifications "ResourceType=security-group,Tags=[{Key=Project,Value=telex},{Key=Name,Value=telex-ec2-sg}]" \
  --region us-east-1

# Authorized Ingress: Ports 80, 443, 22
aws ec2 authorize-security-group-ingress --group-id sg-0c2072740d2612046 --protocol tcp --port 80 --cidr 0.0.0.0/0 --region us-east-1
aws ec2 authorize-security-group-ingress --group-id sg-0c2072740d2612046 --protocol tcp --port 443 --cidr 0.0.0.0/0 --region us-east-1
aws ec2 authorize-security-group-ingress --group-id sg-0c2072740d2612046 --protocol tcp --port 22 --cidr 0.0.0.0/0 --region us-east-1

# 3. Created RDS Security Group & Locked to EC2 SG
aws ec2 create-security-group \
  --group-name telex-rds-sg \
  --description "Telex RDS PostgreSQL Security Group" \
  --vpc-id vpc-0aeec9ca9d2a97c26 \
  --tag-specifications "ResourceType=security-group,Tags=[{Key=Project,Value=telex},{Key=Name,Value=telex-rds-sg}]" \
  --region us-east-1

aws ec2 authorize-security-group-ingress \
  --group-id sg-0d3bdcde4c846de6b \
  --protocol tcp --port 5432 \
  --source-group sg-0c2072740d2612046 \
  --region us-east-1

# 4. Created RDS Subnet Group
aws rds create-db-subnet-group \
  --db-subnet-group-name telex-rds-subnets \
  --db-subnet-group-description "Telex RDS Subnet Group" \
  --subnet-ids subnet-062f972ddbae44225 subnet-07c124ce3603a1590 \
  --tags Key=Project,Value=telex \
  --region us-east-1

# 5. Stored Master DB Password in SSM Parameter Store
aws ssm put-parameter \
  --name "/telex/production/db_password" \
  --value "******" \
  --type "SecureString" \
  --tags "Key=Project,Value=telex" \
  --region us-east-1

# 6. Created RDS PostgreSQL Instance
aws rds create-db-instance \
  --db-instance-identifier telex-db \
  --db-instance-class db.t4g.micro \
  --engine postgres \
  --engine-version 16.4 \
  --master-username telex \
  --master-user-password "******" \
  --allocated-storage 20 \
  --storage-type gp3 \
  --db-name telex \
  --vpc-security-group-ids sg-0d3bdcde4c846de6b \
  --db-subnet-group-name telex-rds-subnets \
  --no-publicly-accessible \
  --backup-retention-period 1 \
  --no-multi-az \
  --no-auto-minor-version-upgrade \
  --no-enable-performance-insights \
  --tags Key=Project,Value=telex \
  --region us-east-1

# 7. Launched EC2 t3.small Ubuntu 24.04 Instance
aws ec2 run-instances \
  --image-id ami-0045d7fc2ad003464 \
  --instance-type t3.small \
  --key-name telex-key \
  --security-group-ids sg-0c2072740d2612046 \
  --subnet-id subnet-062f972ddbae44225 \
  --block-device-mappings file://scratch/mapping.json \
  --user-data file://scratch/userdata.sh \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Project,Value=telex},{Key=Name,Value=telex-api-server}]" "ResourceType=volume,Tags=[{Key=Project,Value=telex},{Key=Name,Value=telex-api-root-vol}]" \
  --region us-east-1

# 8. Allocated & Associated Elastic IP
aws ec2 allocate-address --domain vpc --tag-specifications "ResourceType=elastic-ip,Tags=[{Key=Project,Value=telex},{Key=Name,Value=telex-api-eip}]" --region us-east-1
aws ec2 associate-address --instance-id i-00c45f6bc03841d7a --allocation-id eipalloc-05b2465eba59f43a2 --region us-east-1
```

---

## 4. Verification & Operational Health Check

- **EC2 Instance**: `184.194.145.93` (`i-00c45f6bc03841d7a`)
- **Domain**: `https://184-194-145-93.sslip.io`
- **Database Migrations**: Successfully applied `alembic upgrade head` to AWS RDS PostgreSQL.
- **Service Stack**: Docker Compose (`api` FastAPI + embedded worker, `caddy` reverse proxy with automatic TLS certificate provisioning).
- **Live Healthcheck Response**:
```json
{
  "status": "ok",
  "provider": "gemini"
}
```
*HTTP Status 200 OK verified on 2026-10-01.*

