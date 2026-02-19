mod tests {
    use reqwest;
    use serde_json;
    use clap::{App, Arg};

    #[derive(Debug)]
    struct JiraIssue {
        key: String,
        summary: String,
        status: String,
    }

    fn main() -> Result<(), Box<dyn std::error::Error>> {
        let app = App::new("Rust Agent for Jira")
            .version("1.0")
            .about("Track issues in Jira using Rust Agent");

        let matches = app.get_matches();

        let token = matches.value_of("token").unwrap();
        let project_key = matches.value_of("project-key").unwrap();
        let issue_key = matches.value_of("issue-key").unwrap();

        let url = format!("https://api.atlassian.com/jira/rest/api/2/issue/{}", issue_key);

        let client = reqwest::Client::new();

        let response = client.get(url)
            .header("Authorization", &format!("Bearer {}", token))
            .send()?;

        if response.status().is_success() {
            let json: serde_json::Value = response.json()?;
            let issue_data: JiraIssue = serde_json::from_value(json)?;

            println!("Key: {}", issue_data.key);
            println!("Summary: {}", issue_data.summary);
            println!("Status: {}", issue_data.status);
        } else {
            eprintln!("Failed to retrieve issue: {}", response.text()?);
        }

        Ok(())
    }
}