package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
)

// TestCreateJiraIssue tests the createJiraIssue function
func TestCreateJiraIssue(t *testing.T) {
	jiraURL := "https://your-jira-instance.atlassian.net/rest/api/2/issue"
	username := "your-username"
	password := "your-password"
	projectKey := "YOUR_PROJECT_KEY"
	summary := "Test Issue"
	description := "This is a test issue created by Go Agent."

	testCases := []struct {
		name        string
		jiraURL    string
		username   string
		password   string
		projectKey  string
		summary     string
		description string
		expectedID  string
	}{
		{
			name:        "Success with valid inputs",
			jiraURL:    jiraURL,
			username:   username,
			password:   password,
			projectKey:  projectKey,
			summary:     summary,
			description: description,
			expectedID:  "1234567890", // Example ID
		},
		{
			name:        "Error with invalid inputs",
			jiraURL:    jiraURL,
			username:   username,
			password:   password,
			projectKey:  "",
			summary:     "",
			description: "",
			expectedID:  "", // Expected error
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