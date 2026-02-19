package main

import (
	"testing"
)

// TestJiraClientCreateIssue tests the CreateIssue method of JiraAPI
func TestJiraClientCreateIssue(t *testing.T) {
	jira := &JiraAPI{}
	err := jira.CreateIssue("Test Issue", "This is a test issue created by Go Agent")
	if err != nil {
		t.Errorf("Error creating issue: %v", err)
	}
}

// TestGoAgentClientSendStatus tests the SendStatus method of GoAgentAPI
func TestGoAgentClientSendStatus(t *testing.T) {
	goAgent := &GoAgentAPI{}
	err := goAgent.SendStatus("Running")
	if err != nil {
		t.Errorf("Error sending status: %v", err)
	}
}

// TestJiraIntegrationIntegrate tests the Integrate method of JiraIntegration
func TestJiraIntegrationIntegrate(t *testing.T) {
	jira := &JiraAPI{}
	goAgent := &GoAgentAPI{}

	integration := &JiraIntegration{jira, goAgent}
	err := integration.Integrate()
	if err != nil {
		t.Errorf("Error integrating: %v", err)
	} else {
		fmt.Println("Integration completed successfully!")
	}
}