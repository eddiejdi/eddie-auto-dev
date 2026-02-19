package main

import (
	"testing"
)

func TestJiraClient_CreateIssue(t *testing.T) {
	jira := &JiraAPI{}
	err := jira.CreateIssue("Test Issue", "This is a test issue.")
	if err != nil {
		t.Errorf("CreateIssue failed: %v", err)
	}
}

func TestGoAgentClient_SendStatus(t *testing.T) {
	goAgent := &GoAgentAPI{}
	status, err := goAgent.SendStatus("Running")
	if err != nil {
		t.Errorf("SendStatus failed: %v", err)
	}
	if status != "Running" {
		t.Errorf("Expected 'Running', got '%s'", status)
	}
}

func TestJiraIntegration_Run(t *testing.T) {
	jira := &JiraAPI{}
	goAgent := &GoAgentAPI{}

	integration := &JiraIntegration{jira, goAgent}

	err := integration.Run()
	if err != nil {
		t.Errorf("Run failed: %v", err)
	}
}