package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"testing"
)

func TestCreateJiraIssue(t *testing.T) {
	testCases := []struct {
		jiraURL     string
		username    string
		password    string
		projectKey  string
		summary      string
		description string
		expectedID   string
	}{
		{
			jiraURL:     "https://your-jira-instance.atlassian.net/rest/api/2/issue",
			username:    "your-username",
			password:    "your-password",
			projectKey:  "YOUR_PROJECT_KEY",
			summary:      "Test Issue",
			description: "This is a test issue created by Go Agent.",
			expectedID:   "10100", // Example ID, replace with actual ID
		},
		{
			jiraURL:     "https://your-jira-instance.atlassian.net/rest/api/2/issue",
			username:    "your-username",
			password:    "your-password",
			projectKey:  "YOUR_PROJECT_KEY",
			summary:      "",
			description: "This is a test issue created by Go Agent.",
			expectedID:   "", // Expected error
		},
	}

	for _, tc := range testCases {
		t.Run(fmt.Sprintf("CreateJiraIssue_%s", tc.summary), func(t *testing.T) {
			createdIssue, err := createJiraIssue(tc.jiraURL, tc.username, tc.password, tc.projectKey, tc.summary, tc.description)
			if err != nil {
				fmt.Println("Error creating Jira issue:", err)
				return
			}

			if createdIssue.ID != tc.expectedID {
				t.Errorf("Expected ID: %s, Got: %s", tc.expectedID, createdIssue.ID)
			}
		})
	}
}