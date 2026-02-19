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

    // Function to add an issue to the agent
    fn add_issue(&mut self, issue: Issue) {
        self.issues.push(issue);
    }

    // Function to print all issues in the agent
    fn print_all_issues(&self) {
        for issue in &self.issues {
            issue.print();
        }
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut rust_agent = RustAgent::new();

    // Add some sample issues
    rust_agent.add_issue(Issue::new("123", "Bug in the Rust Agent", "Open"));
    rust_agent.add_issue(Issue::new("456", "Feature request for better logging", "In Progress"));

    // Print all issues
    rust_agent.print_all_issues();

    Ok(())
}