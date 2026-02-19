package main

import (
	"testing"
)

// TestJiraClientCreateIssue tests the CreateIssue method of JiraClientImpl
func TestJiraClientCreateIssue(t *testing.T) {
	jira := &JiraJiraClientImpl{}
	err := jira.CreateIssue("New Feature Request", "Implement a new feature in the application")
	if err != nil {
		t.Errorf("Failed to create Jira issue: %v", err)
	}
}

// TestGoAgentClientSendStatus tests the SendStatus method of GoAgentClientImpl
func TestGoAgentClientSendStatus(t *testing.T) {
	goAgent := &GoAgentGoAgentClient{}
	err := goAgent.SendStatus("Running tests")
	if err != nil {
		t.Errorf("Failed to send Go Agent status: %v", err)
	}
}

// TestJiraJiraClientCreateIssue tests the CreateIssue method of JiraJiraClient
func TestJiraJiraClientCreateIssue(t *testing.T) {
	jira := &JiraJiraClientImpl{}
	err := jira.CreateIssue("New Feature Request", "Implement a new feature in the application")
	if err != nil {
		t.Errorf("Failed to create Jira issue: %v", err)
	}
}

// TestGoAgentGoAgentClientSendStatus tests the SendStatus method of GoAgentGoAgentClient
func TestGoAgentGoAgentClientSendStatus(t *testing.T) {
	goAgent := &GoAgentGoAgentClient{}
	err := goAgent.SendStatus("Running tests")
	if err != nil {
		t.Errorf("Failed to send Go Agent status: %v", err)
	}
}