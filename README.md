# API Arfevrier

## Project Overview
The **API Arfevrier** is a versatile RESTful API designed to provide a variety of services, including:
- **Anagram Finder**: Generate anagrams for a given sentence.
- **YouTube Integration**: Retrieve video and audio links for YouTube content.
- **SNCF Timetable**: Fetch train schedules and disruptions for specific stations.
- **Subdomain Discovery**: Identify subdomains for a given domain.
- **Backup Status**: Monitor the status of daily and monthly backups.
- **IP and Domain Tools**: Perform WHOIS lookups, DNS queries, and port scans.
- **E-commerce Stock Checker**: Check the availability of products on specific e-commerce platforms.

This API is built using **Flask** and integrates with various external tools and services to deliver its functionality.

## Run
```
$ source .env
$ pm2 start --name api-v2 -i python3 api.arfevrier.fr.py
```

## Features
- **Rate Limiting**: Protects the API from abuse with configurable limits.
- **CORS Support**: Enables cross-origin requests for web applications.
- **Self-Documentation**: Automatically generates API documentation using Flask-Selfdoc.

## Requirements
- Python 3.x
- Flask and required dependencies (see `requirements.txt`)
- External tools like `rclone`, `yt-dlp`, `streamlink`, and `nmap` must be installed.

## Usage
The API provides endpoints for various functionalities. For example:
- `/anagram/<string:sentence>`: Returns anagrams for the given sentence.
- `/youtube/video/<string:id>`: Redirects to the MP4 file of a YouTube video.
- `/nmap/<string:ipv4>`: Returns a list of open ports for a given IP address.

Refer to the API documentation (accessible at the root endpoint `/`) for a complete list of endpoints and their usage.
