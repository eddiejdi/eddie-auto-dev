package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"testing"
)

// TestCreateJiraIssue tests the createJiraIssue function with various scenarios
func TestCreateJiraIssue(t *testing.T) {
	testCases := []struct {
		name        string
		jiraURL     string
		username    string
		password    string
		projectKey  string
		summary     string
		description string
		expected   *JiraIssue
	}{
		{
			name: "Success with valid inputs",
			jiraURL: "https://your-jira-instance.atlassian.net/rest/api/2/issue",
			username: "your-username",
			password: "your-password",
			projectKey: "YOUR-PROJECT-KEY",
			summary:     "Test Issue",
			description: "This is a test issue.",
			expected: &JiraIssue{
				ID:        "10101",
				Key:       "EA-34",
				Summary:   "Test Issue",
				Description: "This is a test issue.",
			},
		},
		{
			name: "Error with invalid project key",
			jiraURL: "https://your-jira-instance.atlassian.net/rest/api/2/issue",
			username: "your-username",
			password: "your-password",
			projectKey: "INVALID-PROJECT-KEY",
			summary:     "Test Issue",
			description: "This is a test issue.",
			expected: nil,
		},
		{
			name: "Error with empty summary",
			jiraURL: "https://your-jira-instance.atlassian.net/rest/api/2/issue",
			username: "your-username",
			password: "your-password",
			projectKey: "YOUR-PROJECT-KEY",
			summary:     "",
			description: "This is a test issue.",
			expected: nil,
		},
		{
			name: "Error with empty description",
			jiraURL: "https://your-jira-instance.atlassian.net/rest/api/2/issue",
			username: "your-username",
			password: "your-password",
			projectKey: "YOUR-PROJECT-KEY",
			summary:     "Test Issue",
			description: "",
			expected: nil,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			issue, err := createJiraIssue(
				tc.jiraURL,
				tc.username,
				tc.password,
				tc.projectKey,
				tc.summary,
				tc.description,
			)
			if err != nil && tc.expected == nil {
				t.Errorf("Expected no error but got: %v", err)
			} else if err != nil && tc.expected != nil {
				t.Errorf("Expected an error but got: %v", err)
			} else if issue != tc.expected {
				t.Errorf("Expected issue to be %v, got %v", tc.expected, issue)
			}
		})
	}
}