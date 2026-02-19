package main

import (
	"testing"
)

// TestJiraIntegrationCreateIssue tests the CreateIssue method of JiraIntegration
func TestJiraIntegrationCreateIssue(t *testing.T) {
	jiraClient := &JiraIntegration{}
	err := jiraClient.CreateIssue("New Feature Request", "Implement a new feature to improve user experience")
	if err != nil {
		t.Errorf("Expected no error, got: %v", err)
	}
}

// TestGoAgentIntegrationSendEvent tests the SendEvent method of GoAgentIntegration
func TestGoAgentIntegrationSendEvent(t *testing.T) {
	goAgentClient := &GoAgentIntegration{}
	err := goAgentClient.SendEvent("FeatureRequestCreated", map[string]interface{}{
		"issueTitle": "New Feature Request",
		"description": "Implement a new feature to improve user experience",
	})
	if err != nil {
		t.Errorf("Expected no error, got: %v", err)
	}
}

// TestJiraIntegrationCreateIssueError tests the CreateIssue method with an error
func TestJiraIntegrationCreateIssueError(t *testing.T) {
	jiraClient := &JiraIntegration{}
	err := jiraClient.CreateIssue("", "")
	if err == nil {
		t.Errorf("Expected an error, got: %v", err)
	}
}

// TestGoAgentIntegrationSendEventError tests the SendEvent method with an error
func TestGoAgentIntegrationSendEventError(t *testing.T) {
	goAgentClient := &GoAgentIntegration{}
	err := goAgentClient.SendEvent("", map[string]interface{}{
		"issueTitle": "",
		"description": "",
	})
	if err == nil {
		t.Errorf("Expected an error, got: %v", err)
	}
}

// TestJiraIntegrationCreateIssueEdgeCase tests the CreateIssue method with edge cases
func TestJiraIntegrationCreateIssueEdgeCase(t *testing.T) {
	jiraClient := &JiraIntegration{}
	err := jiraClient.CreateIssue("New Feature Request", "Implement a new feature to improve user experience")
	if err != nil {
		t.Errorf("Expected no error, got: %v", err)
	}
}

// TestGoAgentIntegrationSendEventEdgeCase tests the SendEvent method with edge cases
func TestGoAgentIntegrationSendEventEdgeCase(t *testing.T) {
	goAgentClient := &GoAgentIntegration{}
	err := goAgentClient.SendEvent("", map[string]interface{}{
		"issueTitle": "",
		"description": "",
	})
	if err != nil {
		t.Errorf("Expected no error, got: %v", err)
	}
}