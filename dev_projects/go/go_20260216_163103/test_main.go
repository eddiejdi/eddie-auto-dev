package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"testing"
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
			jiraURL: "https://your-jira-instance.atlassian.net/rest/api/2/issue",
			username: "your-username",
			password: "your-password",
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
			password:  "",
			projectKey: "YOUR_PROJECT_KEY",
			summary:   "Test Issue",
			description: "This is a test issue created by Go Agent.",
		},
	}

	for _, tc := range testCases {
		t.Run(fmt.Sprintf("CreateJiraIssue(%s, %s, %s, %s)", tc.jiraURL, tc.username, tc.password, tc.projectKey), func(t *testing.T) {
			createdIssue, err := createJiraIssue(tc.jiraURL, tc.username, tc.password, tc.projectKey, tc.summary, tc.description)
			if err != nil {
				t.Errorf("createJiraIssue(%s, %s, %s, %s): expected no error, got: %v", tc.jiraURL, tc.username, tc.password, tc.projectKey, err)
			}

			if createdIssue == nil {
				t.Errorf("createJiraIssue(%s, %s, %s, %s): expected non-nil issue, got: nil", tc.jiraURL, tc.username, tc.password, tc.projectKey)
			}
		})
	}
}