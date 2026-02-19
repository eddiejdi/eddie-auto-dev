package main

import (
	"testing"
)

// TestJiraClientCreateIssue tests the CreateIssue method of JiraClientImpl
func TestJiraClientCreateIssue(t *testing.T) {
	j := &JiraClientImpl{}
	err := j.CreateIssue("Test Issue", "This is a test issue.")
	if err != nil {
		t.Errorf("Error creating Jira issue: %v", err)
	}
}

// TestGoAgentClientSendStatus tests the SendStatus method of GoAgentClientImpl
func TestGoAgentClientSendStatus(t *testing.T) {
	g := &GoAgentClientImpl{}
	err := g.SendStatus("Running")
	if err != nil {
		t.Errorf("Error sending Go Agent status: %v", err)
	}
}

// TestJiraJiraClientCreateIssue tests the CreateIssue method of JiraJiraClient
func TestJiraJiraClientCreateIssue(t *testing.T) {
	j := &JiraJiraClient{}
	err := j.CreateIssue("Test Issue", "This is a test issue.")
	if err != nil {
		t.Errorf("Error creating Jira issue: %v", err)
	}
}

// TestGoAgentGoAgentClientSendStatus tests the SendStatus method of GoAgentGoAgentClient
func TestGoAgentGoAgentClientSendStatus(t *testing.T) {
	g := &GoAgentGoAgentClient{}
	err := g.SendStatus("Running")
	if err != nil {
		t.Errorf("Error sending Go Agent status: %v", err)
	}
}