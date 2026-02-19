package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"testing"
)

type JiraIssue struct {
	ID        string `json:"id"`
	Key       string `json:"key"`
	Summary   string `json:"summary"`
	Description string `json:"description"`
}

func TestCreateJiraIssue(t *testing.T) {
	testCases := []struct {
		name         string
		jiraURL      string
		username    string
		password    string
		projectKey  string
		summary     string
		description string
		expectedID   string
	}{
		{
			name: "Success with valid inputs",
			jiraURL: "https://your-jira-instance.atlassian.net/rest/api/2/issue",
			username: "your-username",
			password: "your-password",
			projectKey: "YOUR_PROJECT_KEY",
			summary:     "Test Issue",
			description: "This is a test issue created by Go Agent.",
			expectedID:   "10000", // Example ID
		},
		{
			name: "Error with invalid project key",
			jiraURL: "https://your-jira-instance.atlassian.net/rest/api/2/issue",
			username: "your-username",
			password: "your-password",
			projectKey: "",
			summary:     "Test Issue",
			description: "This is a test issue created by Go Agent.",
			expectedID:   "",
		},
		{
			name: "Error with invalid summary",
			jiraURL: "https://your-jira-instance.atlassian.net/rest/api/2/issue",
			username: "your-username",
			password: "your-password",
			projectKey: "YOUR_PROJECT_KEY",
			summary:     "",
			description: "This is a test issue created by Go Agent.",
			expectedID:   "",
		},
		{
			name: "Error with invalid description",
			jiraURL: "https://your-jira-instance.atlassian.net/rest/api/2/issue",
			username: "your-username",
			password: "your-password",
			projectKey: "YOUR_PROJECT_KEY",
			summary:     "Test Issue",
			description: "",
			expectedID:   "",
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			createdIssue, err := createJiraIssue(tc.jiraURL, tc.username, tc.password, tc.projectKey, tc.summary, tc.description)
			if err != nil {
				fmt.Println("Error creating Jira issue:", err)
				return
			}

			if createdIssue.ID != tc.expectedID {
				t.Errorf("Expected ID %s but got %s", tc.expectedID, createdIssue.ID)
			}
		})
	}
}