package main

import (
	"testing"
)

// TestGoAgentJiraClientCreateIssue tests the CreateIssue method of goAgentJiraClient.
func TestGoAgentJiraClientCreateIssue(t *testing.T) {
	client := goAgentJiraClient{}

	title := "New Feature Request"
	description := "Implement a new feature for the application."

	err := client.CreateIssue(title, description)
	if err != nil {
		t.Errorf("Error creating issue: %v", err)
	}

	t.Log("Issue created successfully")
}