data "aws_caller_identity" "current" {}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

resource "tls_private_key" "deploy" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "aws_key_pair" "deploy" {
  key_name   = var.key_name
  public_key = tls_private_key.deploy.public_key_openssh
}

resource "local_sensitive_file" "deploy_key" {
  filename        = "${path.module}/../.keys/${var.key_name}.pem"
  content         = tls_private_key.deploy.private_key_pem
  file_permission = "0600"
}

resource "aws_security_group" "wispgen" {
  name        = "${var.project_tag}-sg"
  description = "WISPGen web and SSH access"

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTP redirect"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "SSH admin"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_tag}-sg"
    Project     = var.project_tag
    Environment = var.environment
  }
}

resource "aws_iam_role" "instance" {
  name = "${var.project_tag}-instance-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = {
    Project     = var.project_tag
    Environment = var.environment
  }
}

resource "aws_iam_role_policy" "backup" {
  name = "${var.project_tag}-backup-policy"
  role = aws_iam_role.instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket",
      ]
      Resource = [
        aws_s3_bucket.backups.arn,
        "${aws_s3_bucket.backups.arn}/*",
      ]
    }]
  })
}

resource "aws_iam_instance_profile" "instance" {
  name = "${var.project_tag}-instance-profile"
  role = aws_iam_role.instance.name

  tags = {
    Project     = var.project_tag
    Environment = var.environment
  }
}

resource "aws_s3_bucket" "backups" {
  bucket = "${var.project_tag}-backups-${data.aws_caller_identity.current.account_id}-${var.region}"

  tags = {
    Name        = "${var.project_tag}-backups"
    Project     = var.project_tag
    Environment = var.environment
  }
}

resource "aws_s3_bucket_public_access_block" "backups" {
  bucket = aws_s3_bucket.backups.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "backups" {
  bucket = aws_s3_bucket.backups.id

  versioning_configuration {
    status = "Disabled"
  }
}

resource "aws_instance" "wispgen" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  key_name               = aws_key_pair.deploy.key_name
  vpc_security_group_ids = [aws_security_group.wispgen.id]
  iam_instance_profile   = aws_iam_instance_profile.instance.name
  user_data              = file("${path.module}/userdata.sh")

  root_block_device {
    volume_size           = var.data_volume_size
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = false
  }

  metadata_options {
    http_tokens = "required"
  }

  tags = {
    Name        = var.project_tag
    Project     = var.project_tag
    Environment = var.environment
  }
}

resource "aws_eip" "wispgen" {
  domain   = "vpc"
  instance = aws_instance.wispgen.id

  tags = {
    Name        = "${var.project_tag}-eip"
    Project     = var.project_tag
    Environment = var.environment
  }
}
