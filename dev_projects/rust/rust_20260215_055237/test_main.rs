use std::io::{self, Write};
use std::error::Error;

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

fn main() -> Result<(), Box<dyn Error>> {
    let mut rust_agent = RustAgent::new();

    // Add some sample issues
    rust_agent.add_issue(Issue::new("123", "Bug in the Rust Agent", "Open"));
    rust_agent.add_issue(Issue::new("456", "Feature request for better logging", "In Progress"));

    // Print all issues
    rust_agent.print_all_issues();

    Ok(())
}

// Test cases

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_add_issue() {
        let mut agent = RustAgent::new();
        let issue = Issue::new("123", "Bug in the Rust Agent", "Open");
        agent.add_issue(issue);

        assert_eq!(agent.issues.len(), 1);
        assert_eq!(agent.issues[0].id, "123");
    }

    #[test]
    fn test_add_invalid_issue() {
        let mut agent = RustAgent::new();
        let issue = Issue::new("", "", ""); // Invalid issue
        match agent.add_issue(issue) {
            Err(_) => assert!(true), // Expected error
            Ok(_) => assert!(false), // Expected failure
        }
    }

    #[test]
    fn test_print_all_issues() {
        let mut agent = RustAgent::new();
        let issue1 = Issue::new("123", "Bug in the Rust Agent", "Open");
        let issue2 = Issue::new("456", "Feature request for better logging", "In Progress");
        agent.add_issue(issue1);
        agent.add_issue(issue2);

        agent.print_all_issues();

        assert_eq!(agent.issues.len(), 2);
    }
}