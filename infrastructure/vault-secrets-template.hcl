# HashiCorp Vault Configuration Template for FAOS Secrets
# Usage: Load this into your Vault server to manage all secrets

path "secret/claim2car/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

path "secret/data/claim2car/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

# Database Credentials
path "secret/data/claim2car/postgres" {
  capabilities = ["read", "list"]
}

path "secret/data/claim2car/mongodb" {
  capabilities = ["read", "list"]
}

path "secret/data/claim2car/redis" {
  capabilities = ["read", "list"]
}

# API Keys
path "secret/data/claim2car/square" {
  capabilities = ["read"]
}

path "secret/data/claim2car/resend" {
  capabilities = ["read"]
}

path "secret/data/claim2car/polygon" {
  capabilities = ["read"]
}

# Cryptographic Keys
path "secret/data/claim2car/jwt" {
  capabilities = ["read"]
}

path "secret/data/claim2car/encryption" {
  capabilities = ["read"]
}
