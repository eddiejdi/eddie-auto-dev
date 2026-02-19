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
		name        string
		jiraURL     string
		username    string
		password    string
		projectKey  string
		summary     string
		description string
		expected   JiraIssue
	}{
		{
			name: "Success with valid inputs",
			jiraURL: "https://your-jira-instance.atlassian.net/rest/api/2/issue",
			username: "your-username",
			password: "your-password",
			projectKey: "YOUR-PROJECT-KEY",
			summary:     "Test Issue",
			description: "This is a test issue.",
			expected: JiraIssue{
				ID:        "10100",
				Key:       "EA-34",
				Type:      "Bug",
				Summary:   "Test Issue",
				Description: "This is a test issue.",
			},
		},
		// Add more test cases as needed
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			issue, err := createJiraIssue(tc.jiraURL, tc.username, tc.password, tc.projectKey, tc.summary, tc.description)
			if err != nil {
				t.Errorf("createJiraIssue(%s): %v", tc.jiraURL, err)
				return
			}
			if !reflect.DeepEqual(issue, tc.expected) {
				t.Errorf("createJiraIssue(%s): Expected %+v, got %+v", tc.jiraURL, tc.expected, issue)
			}
		})
	}
}