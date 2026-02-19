use reqwest;
use serde_json::{self, Value};
use clap::Parser;

#[derive(Parser)]
struct Args {
    #[clap(short, long, help = "Jira project key")]
    project_key: String,
    #[clap(short, long, help = "Jira issue ID")]
    issue_id: String,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Args::parse();

    // Jira API endpoint for fetching activity
    let url = format!("https://api.atlassian.com/rest/api/3/project/{}/issue/{}/activity", args.project_key, args.issue_id);

    // Authenticate with Jira API (replace with actual authentication logic)
    let auth = ("your_username", "your_password".to_string());
    let client = reqwest::Client::new();

    // Fetch activity from Jira
    let response = client.get(&url).basic_auth(auth.0, Some(auth.1)).send()?;

    if response.status().is_success() {
        let json: Value = serde_json::from_str(&response.text()?)?;
        println!("Activity for issue {}: {:?}", args.issue_id, json);
    } else {
        eprintln!("Failed to fetch activity: {}", response.text()?);
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use reqwest;
    use serde_json::{self, Value};
    use clap::Parser;

    #[derive(Parser)]
    struct Args {
        #[clap(short, long, help = "Jira project key")]
        project_key: String,
        #[clap(short, long, help = "Jira issue ID")]
        issue_id: String,
    }

    fn main() -> Result<(), Box<dyn std::error::Error>> {
        let args = Args::parse();

        // Jira API endpoint for fetching activity
        let url = format!("https://api.atlassian.com/rest/api/3/project/{}/issue/{}/activity", args.project_key, args.issue_id);

        // Authenticate with Jira API (replace with actual authentication logic)
        let auth = ("your_username", "your_password".to_string());
        let client = reqwest::Client::new();

        // Fetch activity from Jira
        let response = client.get(&url).basic_auth(auth.0, Some(auth.1)).send()?;

        if response.status().is_success() {
            let json: Value = serde_json::from_str(&response.text()?)?;
            println!("Activity for issue {}: {:?}", args.issue_id, json);
        } else {
            eprintln!("Failed to fetch activity: {}", response.text()?);
        }

        Ok(())
    }

    #[test]
    fn test_main_success() {
        // Test case 1: Successful request
        let args = Args {
            project_key: "JIRA".to_string(),
            issue_id: "12345".to_string(),
        };
        let response = reqwest::get("https://api.atlassian.com/rest/api/3/project/JIRA/issues/12345/activity")
            .basic_auth(("your_username", "your_password".to_string()))
            .send();
        assert!(response.is_ok());
    }

    #[test]
    fn test_main_failure() {
        // Test case 2: Failed request
        let args = Args {
            project_key: "JIRA".to_string(),
            issue_id: "12345".to_string(),
        };
        let response = reqwest::get("https://api.atlassian.com/rest/api/3/project/JIRA/issues/12345/activity")
            .basic_auth(("your_username", "your_password".to_string()))
            .send();
        assert!(response.is_err());
    }

    #[test]
    fn test_main_invalid_project_key() {
        // Test case 3: Invalid project key
        let args = Args {
            project_key: "".to_string(),
            issue_id: "12345".to_string(),
        };
        let response = reqwest::get("https://api.atlassian.com/rest/api/3/project/JIRA/issues/12345/activity")
            .basic_auth(("your_username", "your_password".to_string()))
            .send();
        assert!(response.is_err());
    }

    #[test]
    fn test_main_invalid_issue_id() {
        // Test case 4: Invalid issue ID
        let args = Args {
            project_key: "JIRA".to_string(),
            issue_id: "".to_string(),
        };
        let response = reqwest::get("https://api.atlassian.com/rest/api/3/project/JIRA/issues/12345/activity")
            .basic_auth(("your_username", "your_password".to_string()))
            .send();
        assert!(response.is_err());
    }
}