use reqwest;
use serde_json;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn connect_to_rust_agent_success() {
        let config = RustAgentConfig {
            host: "localhost".to_string(),
            port: 8080,
        };
        let response = connect_to_rust_agent(&config).unwrap();
        assert_eq!(response, "Success message");
    }

    #[test]
    fn connect_to_rust_agent_failure() {
        let config = RustAgentConfig {
            host: "localhost".to_string(),
            port: 8080,
        };
        let response = connect_to_rust_agent(&config).unwrap_err();
        assert_eq!(response, "Failed to connect to Rust Agent");
    }

    #[test]
    fn update_jira_description_success() {
        let config = RustAgentConfig {
            host: "localhost".to_string(),
            port: 8080,
        };
        let response = update_jira_description("ABC123", "This is a new description for the issue.").unwrap();
        assert_eq!(response, "Success message");
    }

    #[test]
    fn update_jira_description_failure() {
        let config = RustAgentConfig {
            host: "localhost".to_string(),
            port: 8080,
        };
        let response = update_jira_description("ABC123", "").unwrap_err();
        assert_eq!(response, "Failed to update Jira description");
    }
}