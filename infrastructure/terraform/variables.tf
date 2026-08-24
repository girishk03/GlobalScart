variable "project_id" {
  description = "Google Cloud project ID"
  type        = string
  default     = "elite-matter-452317-g8"
}

variable "region" {
  description = "Google Cloud region"
  type        = string
  default     = "asia-south1"
}

variable "bucket_location" {
  description = "GCS bucket location"
  type        = string
  default     = "ASIA-SOUTH1"
}

variable "bucket_name" {
  description = "Globally unique GCS bucket name"
  type        = string
  default     = "elite-matter-452317-g8-globalcart-raw"
}
