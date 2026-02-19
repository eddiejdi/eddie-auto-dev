package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
)

// TestCreateJiraIssue tests the createJiraIssue function with various scenarios
func TestCreateJiraIssue(t *testing.T) {
	testCases := []struct {
		jiraURL       string
		username     string
		password     string
		projectKey    string
		summary      string
		description  string
		expectedID   string
		expectedErr error
	}{
		{
			jiraURL: "https://your-jira-instance.atlassian.net/rest/api/2/issue",
			username: "your-username",
			password: "your-password",
			projectKey: "YOUR_PROJECT_KEY",
			summary:      "Test Issue",
			description:  "This is a test issue created by Go Agent.",
			expectedID:   "10100", // Example ID
		},
		{
			jiraURL: "https://your-jira-instance.atlassian.net/rest/api/2/issue",
			username: "your-username",
			password: "your-password",
			projectKey: "YOUR_PROJECT_KEY",
			summary:      "",
			description:  "",
			expectedErr: fmt.Errorf("Error creating issue: summary and description cannot be empty"),
		},
		{
			jiraURL: "https://your-jira-instance.atlassian.net/rest/api/2/issue",
			username: "your-username",
			password: "your-password",
			projectKey: "YOUR_PROJECT_KEY",
			summary:      "Test Issue",
			description:  "This is a test issue created by Go Agent.",
			expectedErr: fmt.Errorf("Error creating issue: summary cannot be empty"),
		},
		{
			jiraURL: "https://your-jira-instance.atlassian.net/rest/api/2/issue",
			username: "your-username",
			password: "your-password",
			projectKey: "YOUR_PROJECT_KEY",
			summary:      "Test Issue",
			description:  "This is a test issue created by Go Agent.",
			expectedErr: fmt.Errorf("Error creating issue: description cannot be empty"),
		},
	}

	for _, tc := range testCases {
		t.Run(fmt.Sprintf("CreateJiraIssue_%s", tc.summary), func(t *testing.T) {
			issue, err := createJiraIssue(tc.jiraURL, tc.username, tc.password, tc.projectKey, tc.summary, tc.description)
			if err != nil && err.Error() != tc.expectedErr.Error() {
				t.Errorf("Expected error: %v, got: %v", tc.expectedErr, err)
			} else if err == nil && issue.ID != tc.expectedID {
				t.Errorf("Expected ID: %s, got: %s", tc.expectedID, issue.ID)
			}
		})
	}
}