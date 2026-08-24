output "raw_bucket_name" {
  description = "Name of the GlobalScart raw GCS bucket"
  value       = google_storage_bucket.raw_data.name
}

output "raw_bucket_url" {
  description = "GCS URL of the raw bucket"
  value       = "gs://${google_storage_bucket.raw_data.name}"
}
