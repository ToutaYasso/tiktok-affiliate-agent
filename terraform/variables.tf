variable "resource_group_name" {
  description = "Nom du resource group Azure"
  type        = string
  default     = "affiliate-bot-rg"
}

variable "location" {
  description = "Region Azure"
  type        = string
  default     = "francecentral"
}

variable "storage_account_name" {
  description = "Nom unique du storage account (minuscules, max 24 chars)"
  type        = string
  default     = "affiliatebotstorage"
}

variable "key_vault_name" {
  description = "Nom unique du Key Vault"
  type        = string
  default     = "affiliate-kv"
}

variable "ssh_public_key_path" {
  description = "Chemin vers la cle SSH publique"
  type        = string
  default     = "~/.ssh/id_rsa.pub"
}

variable "admin_ip" {
  description = "Ton IP pour autoriser SSH (format: x.x.x.x/32)"
  type        = string
}

variable "tags" {
  description = "Tags Azure"
  type        = map(string)
  default = {
    project     = "tiktok-affiliate-agent"
    environment = "production"
    owner       = "ToutaYasso"
  }
}
