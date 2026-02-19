use std::error::Error;
use std::io::{self, Write};

// Define a struct to represent the Jira issue
struct Issue {
    id: String,
    summary: String,
    status: String,
}

impl Issue {
    fn new(id: &str, summary: &str, status: &str) -> Self {
        Issue {
            id: id.to_string(),
            summary: summary.to_string(),
            status: status.to_string(),
        }
    }

    fn print(&self) {
        println!("Issue ID: {}", self.id);
        println!("Summary: {}", self.summary);
        println!("Status: {}", self.status);
    }
}

// Define a struct to represent the Rust Agent
struct RustAgent {
    issues: Vec<Issue>,
}

impl RustAgent {
    fn new() -> Self {
        RustAgent { issues: Vec::new() }
    }

    fn add_issue(&mut self, issue: Issue) {
        self.issues.push(issue);
    }

    fn print_issues(&self) {
        for issue in &self.issues {
            issue.print();
        }
    }
}

// Define a struct to represent the CLI application
struct CliApp {
    agent: RustAgent,
}

impl CliApp {
    fn new() -> Self {
        CliApp { agent: RustAgent::new() }
    }

    fn add_issue(&mut self, id: &str, summary: &str, status: &str) {
        let issue = Issue::new(id, summary, status);
        self.agent.add_issue(issue);
    }

    fn print_issues(&self) {
        self.agent.print_issues();
    }
}

fn main() -> Result<(), Box<dyn Error>> {
    let mut app = CliApp::new();

    // Example usage
    app.add_issue("123", "Fix bug in Rust Agent", "In Progress");
    app.add_issue("456", "Add new feature to Rust Agent", "To Do");

    app.print_issues();

    Ok(())
}