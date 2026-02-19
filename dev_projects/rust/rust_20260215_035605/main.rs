use std::fs;
use std::io::{self, BufRead};
use std::path::Path;

#[derive(Debug)]
struct JiraIssue {
    id: String,
    summary: String,
    status: String,
}

impl JiraIssue {
    fn new(id: &str, summary: &str, status: &str) -> Self {
        JiraIssue {
            id: id.to_string(),
            summary: summary.to_string(),
            status: status.to_string(),
        }
    }

    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "id": self.id.clone(),
            "summary": self.summary.clone(),
            "status": self.status.clone()
        })
    }
}

#[derive(Debug)]
struct JiraClient {
    issues: Vec<JiraIssue>,
}

impl JiraClient {
    fn new() -> Self {
        JiraClient { issues: Vec::new() }
    }

    fn add_issue(&mut self, issue: JiraIssue) {
        self.issues.push(issue);
    }

    fn save_issues_to_file(&self, filename: &str) -> io::Result<()> {
        let mut file = fs::File::create(filename)?;
        for issue in &self.issues {
            writeln!(file, "{}", issue.to_json())?;
        }
        Ok(())
    }
}

#[derive(Debug)]
struct JiraCli {
    client: JiraClient,
}

impl JiraCli {
    fn new() -> Self {
        JiraCli { client: JiraClient::new() }
    }

    fn add_issue(&mut self, id: &str, summary: &str, status: &str) {
        let issue = JiraIssue::new(id, summary, status);
        self.client.add_issue(issue);
    }

    fn save_issues_to_file(&self, filename: &str) -> io::Result<()> {
        self.client.save_issues_to_file(filename)
    }
}

fn main() -> io::Result<()> {
    let mut cli = JiraCli::new();

    // Simulando a entrada do usuário
    println!("Enter issue ID:");
    let id = io::stdin().read_line()?;
    println!("Enter issue summary:");
    let summary = io::stdin().read_line()?;
    println!("Enter issue status:");
    let status = io::stdin().read_line()?;

    cli.add_issue(&id, &summary, &status);

    println!("Issues saved to issues.json");

    Ok(())
}