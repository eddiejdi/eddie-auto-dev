#[cfg(test)]
mod tests {
    use reqwest;
    use serde_json::{self, Value};
    use clap::Parser;

    #[derive(Parser)]
    struct Args {
        #[clap(short, long, help = "Jira server URL")]
        jira_url: String,

        #[clap(short, long, help = "Jira username")]
        username: String,

        #[clap(short, long, help = "Jira password")]
        password: String,

        #[clap(subcommand)]
        command: Command,
    }

    #[derive(Parser)]
    enum Command {
        CreateIssue {
            title: String,
            description: String,
        },
        UpdateIssue {
            issue_key: String,
            title: Option<String>,
            description: Option<String>,
        },
        DeleteIssue {
            issue_key: String,
        },
    }

    fn main() -> Result<(), Box<dyn std::error::Error>> {
        let args = Args::parse();

        match args.command {
            Command::CreateIssue { title, description } => create_issue(&args.jira_url, &args.username, &args.password, title, description),
            Command::UpdateIssue { issue_key, title: new_title, description: new_description } => update_issue(&args.jira_url, &args.username, &args.password, issue_key, new_title, new_description),
            Command::DeleteIssue { issue_key } => delete_issue(&args.jira_url, &args.username, &args.password, issue_key),
        }
    }

    fn create_issue(url: &str, username: &str, password: &str, title: String, description: String) -> Result<(), Box<dyn std::error::Error>> {
        let data = json!({
            "fields": {
                "project": {"key": "YOUR_PROJECT_KEY"},
                "summary": title,
                "description": description,
                "issuetype": {"name": "Bug"}
            }
        });

        let response = reqwest::post(format!("{}rest/api/2/issue", url))
            .basic_auth(username, password)
            .json(&data)
            .send()?;

        if response.status().is_success() {
            println!("Issue created successfully!");
        } else {
            eprintln!("Failed to create issue: {}", response.text()?);
        }

        Ok(())
    }

    fn update_issue(url: &str, username: &str, password: &str, issue_key: String, new_title: Option<String>, new_description: Option<String>) -> Result<(), Box<dyn std::error::Error>> {
        let mut data = json!({
            "fields": {}
        });

        if let Some(new_title) = new_title {
            data["fields"]["summary"] = new_title;
        }

        if let Some(new_description) = new_description {
            data["fields"]["description"] = new_description;
        }

        let response = reqwest::put(format!("{}rest/api/2/issue/{}", url, issue_key))
            .basic_auth(username, password)
            .json(&data)
            .send()?;

        if response.status().is_success() {
            println!("Issue updated successfully!");
        } else {
            eprintln!("Failed to update issue: {}", response.text()?);
        }

        Ok(())
    }

    fn delete_issue(url: &str, username: &str, password: &str, issue_key: String) -> Result<(), Box<dyn std::error::Error>> {
        let response = reqwest::delete(format!("{}rest/api/2/issue/{}", url, issue_key))
            .basic_auth(username, password)
            .send()?;

        if response.status().is_success() {
            println!("Issue deleted successfully!");
        } else {
            eprintln!("Failed to delete issue: {}", response.text()?);
        }

        Ok(())
    }
}