use reqwest;
use serde_json;

// Define a struct to represent a Jira issue
#[derive(Debug, Serialize)]
struct Issue {
    key: String,
    summary: String,
    description: String,
}

fn create_issue(jira_url: &str, username: &str, password: &str, issue: &Issue) -> Result<(), reqwest::Error> {
    let url = format!("{}/rest/api/2/issue", jira_url);
    let json_body = serde_json::to_string(issue)?;

    let response = reqwest::Client::new()
        .post(url)
        .basic_auth(username, password)
        .header("Content-Type", "application/json")
        .body(json_body)
        .send()?;

    if response.status().is_success() {
        Ok(())
    } else {
        Err(reqwest::Error::from(response))
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_url = "https://your-jira-instance.atlassian.net";
    let username = "your-username";
    let password = "your-password";

    // Test case 1: Successful creation of an issue
    let issue = Issue {
        key: "TEST-123".to_string(),
        summary: "Test Jira Integration".to_string(),
        description: "This is a test to integrate Rust Agent with Jira.".to_string(),
    };
    assert!(create_issue(jira_url, username, password, &issue).is_ok());

    // Test case 2: Error when creating an issue with invalid JSON
    let invalid_json = r#"{"key": "TEST-123", "summary": "Test Jira Integration", "description": "This is a test to integrate Rust Agent with Jira."}"#;
    assert!(create_issue(jira_url, username, password, &serde_json::from_str::<Issue>(invalid_json).unwrap()).is_err());

    // Test case 3: Error when creating an issue with missing fields
    let missing_field_issue = Issue {
        key: "TEST-124".to_string(),
        summary: "Test Jira Integration".to_string(),
        description: "".to_string(),
    };
    assert!(create_issue(jira_url, username, password, &missing_field_issue).is_err());

    // Test case 4: Error when creating an issue with invalid credentials
    let invalid_credentials_issue = Issue {
        key: "TEST-125".to_string(),
        summary: "Test Jira Integration".to_string(),
        description: "This is a test to integrate Rust Agent with Jira.".to_string(),
    };
    assert!(create_issue(jira_url, "invalid", password, &invalid_credentials_issue).is_err());

    println!("All tests passed!");

    Ok(())
}