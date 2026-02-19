package main

import (
	"fmt"
	"net/http"
	"testing"
)

// TestNewJiraClient tests the NewJiraClient function.
func TestNewJiraClient(t *testing.T) {
	client := NewJiraClient("https://your-jira-instance.atlassian.net")
	if client == nil {
		t.Errorf("NewJiraClient returned nil")
	}
}

// TestCreateIssue tests the CreateIssue function.
func TestCreateIssue(t *testing.T) {
	client := NewJiraClient("https://your-jira-instance.atlassian.net")

	testCases := []struct {
		name     string
		baseURL  string
		summary   string
		description string
	}{
		{"valid inputs", "https://your-jira-instance.atlassian.net", "Bug in Go Agent", "Go Agent is not working as expected."},
		{"invalid summary", "https://your-jira-instance.atlassian.net", "", "Go Agent is not working as expected."},
		{"invalid description", "https://your-jira-instance.atlassian.net", "Bug in Go Agent", ""},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			client.baseURL = tc.baseURL
			err := client.CreateIssue(tc.summary, tc.description)
			if err != nil {
				t.Errorf("CreateIssue failed with error: %v", err)
			}
		})
	}
}