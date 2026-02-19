package main

import (
	"testing"
)

func TestJiraClient_CreateIssue(t *testing.T) {
	jiraClient := &JiraClient{
		client: jira.NewClient("YOUR_JIRA_URL", "YOUR_API_TOKEN"),
	}

	summary := "Test Issue"
	description := "This is a test issue."

	issue, err := jiraClient.CreateIssue(summary, description)
	if err != nil {
		t.Errorf("Error creating issue: %s", err)
	}
	if issue == nil {
		t.Errorf("Issue should not be nil")
	}
}

func TestJiraClient_GetIssues(t *testing.T) {
	jiraClient := &JiraClient{
		client: jira.NewClient("YOUR_JIRA_URL", "YOUR_API_TOKEN"),
	}

	issues, err := jiraClient.GetIssues()
	if err != nil {
		t.Errorf("Error getting issues: %s", err)
	}
	if len(issues) == 0 {
		t.Errorf("Expected at least one issue")
	}
}