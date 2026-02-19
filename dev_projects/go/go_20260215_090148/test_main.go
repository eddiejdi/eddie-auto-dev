package main

import (
	"testing"
)

// TestJiraAPICreateIssue tests the CreateIssue method of JiraAPI
func TestJiraAPICreateIssue(t *testing.T) {
	jira := &JiraAPI{}
	err := jira.CreateIssue("Test Issue", "This is a test issue.")
	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}
}

// TestGoAgentAPISendStatus tests the SendStatus method of GoAgentAPI
func TestGoAgentAPISendStatus(t *testing.T) {
	goAgent := &GoAgentAPI{}
	err := goAgent.SendStatus("Running")
	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}
}

// TestJiraIntegrationRun tests the Run method of JiraIntegration
func TestJiraIntegrationRun(t *testing.T) {
	jiraAPI := &JiraAPI{}
	goAgentAPI := &GoAgentAPI{}

	integration := &JiraIntegration{jiraClient: jiraAPI, goAgentClient: goAgentAPI}
	err := integration.Run()
	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}
}