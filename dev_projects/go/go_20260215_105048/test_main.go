package main_test

import (
	"testing"
)

func TestJiraClient_CreateIssue(t *testing.T) {
	jira := &JiraAPI{}

	testCases := []struct {
		name     string
		title    string
		description string
	}{
		{"Success", "Test Issue", "This is a test issue created by the Go Agent."},
		{"Error", "", "Invalid title"},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			err := jira.CreateIssue(tc.title, tc.description)
			if err != nil {
				t.Errorf("CreateIssue(%q, %q) = %v; want no error", tc.title, tc.description, err)
			}
		})
	}
}