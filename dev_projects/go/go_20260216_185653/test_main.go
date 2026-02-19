package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
)

// TestCreateJiraIssue tests the createJiraIssue function with various inputs
func TestCreateJiraIssue(t *testing.T) {
	testCases := []struct {
		jiraURL    string
		username  string
		password  string
		projectKey string
		summary   string
		description string
	}{
		{
			jiraURL:    "https://your-jira-instance.atlassian.net/rest/api/2/issue",
			username:  "your-username",
			password:  "your-password",
			projectKey: "YOUR_PROJECT_KEY",
			summary:   "Test Issue",
			description: "This is a test issue created by Go Agent.",
		},
		{
			jiraURL:    "https://your-jira-instance.atlassian.net/rest/api/2/issue",
			username:  "your-username",
			password:  "your-password",
			projectKey: "YOUR_PROJECT_KEY",
			summary:   "",
			description: "This is a test issue created by Go Agent.",
		},
		{
			jiraURL:    "https://your-jira-instance.atlassian.net/rest/api/2/issue",
			username:  "your-username",
			password:  "your-password",
			projectKey: "",
			summary:   "Test Issue",
			description: "This is a test issue created by Go Agent.",
		},
		{
			jiraURL:    "https://your-jira-instance.atlassian.net/rest/api/2/issue",
			username:  "your-username",
			password:  "your-password",
			projectKey: "YOUR_PROJECT_KEY",
			summary:   "Test Issue",
			description: "",
		},
	}

	for _, tc := range testCases {
		t.Run(fmt.Sprintf("CreateJiraIssue with %s", tc.summary), func(t *testing.T) {
			createdIssue, err := createJiraIssue(tc.jiraURL, tc.username, tc.password, tc.projectKey, tc.summary, tc.description)
			if err != nil {
				t.Errorf("Error creating Jira issue: %v", err)
			}

			// Add assertions to check the created issue
			// For example:
			// assert.Equal(t, "Test Issue", createdIssue.Summary)
		})
	}
}