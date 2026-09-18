output "vm_public_ip" {
  description = "IP publique de la VM"
  value       = azurerm_public_ip.main.ip_address
}

output "vm_ssh_command" {
  description = "Commande SSH pour se connecter a la VM"
  value       = "ssh azureuser@${azurerm_public_ip.main.ip_address}"
}

output "storage_connection_string" {
  description = "Connection string Azure Blob (sensible)"
  value       = azurerm_storage_account.main.primary_connection_string
  sensitive   = true
}

output "key_vault_uri" {
  description = "URI du Key Vault"
  value       = azurerm_key_vault.main.vault_uri
}
