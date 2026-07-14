output "public_ip" {
  description = "Elastic IP assigned to the WISPGen instance. Point *.app.wisp.llc and app.wisp.llc A records here."
  value       = aws_eip.wispgen.public_ip
}

output "instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.wispgen.id
}

output "backup_bucket_name" {
  description = "S3 bucket for tenant database backups"
  value       = aws_s3_bucket.backups.bucket
}

output "ssh_command" {
  description = "SSH command to access the instance"
  value       = "ssh -i ${local_sensitive_file.deploy_key.filename} ubuntu@${aws_eip.wispgen.public_ip}"
}

output "key_file_path" {
  description = "Path to the generated SSH private key"
  value       = local_sensitive_file.deploy_key.filename
  sensitive   = true
}
