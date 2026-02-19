use reqwest;
use serde_json;

// Define a struct to represent the Rust Agent configuration
#[derive(Debug)]
struct RustAgentConfig {
    host: String,
    port: u16,
}

// Define a struct to represent the Jira API response
#[derive(Debug, Deserialize)]
struct JiraResponse {
    key: String,
    fields: Fields,
}

// Define a struct to represent the Jira fields
#[derive(Debug, Deserialize)]
struct Fields {
    description: Option<String>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Create an instance of RustAgentConfig
    let config = RustAgentConfig {
        host: "localhost".to_string(),
        port: 8080,
    };

    // Connect to the Rust Agent and send a message
    let response = connect_to_rust_agent(&config)?;

    // Parse the JSON response from the Rust Agent
    let parsed_response: JiraResponse = serde_json::from_str(&response)?;

    // Update the description field in Jira
    update_jira_description(parsed_response.key, "This is a new description for the issue.")?;

    Ok(())
}

fn connect_to_rust_agent(config: &RustAgentConfig) -> Result<String, Box<dyn std::error::Error>> {
    let url = format!("http://{}/api/v1/agent", config.host);
    let response = reqwest::get(&url)?;
    if !response.status().is_success() {
        return Err(format!("Failed to connect to Rust Agent: {}", response.text())?.into());
    }
    Ok(response.text()?)
}

fn update_jira_description(issue_key: &str, description: &str) -> Result<(), Box<dyn std::error::Error>> {
    let url = format!("http://{}/api/v1/issue/{}/update", config.host, issue_key);
    let payload = serde_json::json!({
        "fields": {
            "description": description
        }
    });
    let response = reqwest::put(&url)
        .header("Content-Type", "application/json")
        .body(payload.to_string())
        .send()?;
    if !response.status().is_success() {
        return Err(format!("Failed to update Jira description: {}", response.text())?.into());
    }
    Ok(())
}