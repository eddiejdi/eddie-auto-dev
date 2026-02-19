package main

import (
	"testing"
)

// TestJiraIntegrationCreateIssue tests the CreateIssue method of JiraIntegration
func TestJiraIntegrationCreateIssue(t *testing.T) {
	jira := &JiraIntegration{}
	err := jira.CreateIssue("Test Issue", "This is a test issue.")
	if err != nil {
		t.Errorf("Expected no error, got: %v", err)
	}
}

// TestGoAgentIntegrationSendStatus tests the SendStatus method of GoAgentIntegration
func TestGoAgentIntegrationSendStatus(t *testing.T) {
	goAgent := &GoAgentIntegration{}
	err := goAgent.SendStatus("Running")
	if err != nil {
		t.Errorf("Expected no error, got: %v", err)
	}
}

// TestJiraIntegrationCreateIssueError tests the CreateIssue method with an error
func TestJiraIntegrationCreateIssueError(t *testing.T) {
	jira := &JiraIntegration{}
	err := jira.CreateIssue("", "")
	if err == nil {
		t.Errorf("Expected an error, got: %v", err)
	}
}

// TestGoAgentIntegrationSendStatusError tests the SendStatus method with an error
func TestGoAgentIntegrationSendStatusError(t *testing.T) {
	goAgent := &GoAgentIntegration{}
	err := goAgent.SendStatus("")
	if err == nil {
		t.Errorf("Expected an error, got: %v", err)
	}
}