package main

import (
	"testing"
)

func TestJiraClient_CreateIssue(t *testing.T) {
	jira := &JiraClient{
		url:    "https://your-jira-instance.atlassian.net",
		token:  "your-jira-token",
	}

	testCases := []struct {
		title     string
		description string
		expected error
	}{
		{"Test Issue", "This is a test issue for the Go Agent with Jira integration.", nil},
		// Add more test cases as needed
	}

	for _, tc := range testCases {
		t.Run(fmt.Sprintf("CreateIssue(%s, %s)", tc.title, tc.description), func(t *testing.T) {
			err := jira.CreateIssue(tc.title, tc.description)
			if err != nil && err.Error() != tc.expected.Error() {
				t.Errorf("Expected error: %v, got: %v", tc.expected, err)
			}
		})
	}
}