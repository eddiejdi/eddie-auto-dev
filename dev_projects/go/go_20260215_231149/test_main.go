package main_test

import (
	"testing"
)

// TestJiraClientCreateIssue tests the CreateIssue method of JiraService
func TestJiraClientCreateIssue(t *testing.T) {
	jira := &JiraService{}
	err := jira.CreateIssue("New Feature Request", "Implement a new feature in the application.")
	if err != nil {
		t.Errorf("Expected no error, got: %v", err)
	}
}

// TestGoAgentClientSendEvent tests the SendEvent method of GoAgentService
func TestGoAgentClientSendEvent(t *testing.T) {
	goAgent := &GoAgentService{}
	err := goAgent.SendEvent("feature_request_created", map[string]interface{}{
		"issue_title": "New Feature Request",
		"description": "Implement a new feature in the application.",
	})
	if err != nil {
		t.Errorf("Expected no error, got: %v", err)
	}
}

// TestJiraClientCreateIssueError tests the CreateIssue method with an error case
func TestJiraClientCreateIssueError(t *testing.T) {
	jira := &JiraService{}
	err := jira.CreateIssue("", "Implement a new feature in the application.")
	if err == nil {
		t.Errorf("Expected an error, got: %v", err)
	}
}

// TestGoAgentClientSendEventError tests the SendEvent method with an error case
func TestGoAgentClientSendEventError(t *testing.T) {
	goAgent := &GoAgentService{}
	err := goAgent.SendEvent("", map[string]interface{}{
		"issue_title": "New Feature Request",
		"description": "Implement a new feature in the application.",
	})
	if err == nil {
		t.Errorf("Expected an error, got: %v", err)
	}
}

// TestJiraClientCreateIssueEdgeCase tests the CreateIssue method with edge cases
func TestJiraClientCreateIssueEdgeCase(t *testing.T) {
	jira := &JiraService{}
	err := jira.CreateIssue("New Feature Request", "Implement a new feature in the application.")
	if err != nil {
		t.Errorf("Expected no error, got: %v", err)
	}
}

// TestGoAgentClientSendEventEdgeCase tests the SendEvent method with edge cases
func TestGoAgentClientSendEventEdgeCase(t *testing.T) {
	goAgent := &GoAgentService{}
	err := goAgent.SendEvent("", map[string]interface{}{
		"issue_title": "New Feature Request",
		"description": "Implement a new feature in the application.",
	})
	if err != nil {
		t.Errorf("Expected no error, got: %v", err)
	}
}