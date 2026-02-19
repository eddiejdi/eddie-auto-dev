package main

import (
	"testing"
)

func TestScrum11_CreateIssue(t *testing.T) {
	jira := &JiraAPI{}
	goAgent := &GoAgentAPI{}

	scrum11 := &Scrum11{jira, goAgent}

	testCases := []struct {
		title    string
		description string
	}{
		{"Bug in Go Agent", "The Go Agent is not working as expected."},
		{"Feature Request", "New feature added to the product."},
		{"Invalid Title", ""},
		{"Empty Description", "None"},
	}

	for _, tc := range testCases {
		t.Run(fmt.Sprintf("CreateIssue(%s, %s)", tc.title, tc.description), func(t *testing.T) {
			err := scrum11.CreateIssue(tc.title, tc.description)
			if err != nil {
				t.Errorf("CreateIssue(%s, %s) failed: %v", tc.title, tc.description, err)
			}
		})
	}

	testCasesError := []struct {
		title    string
		description string
	}{
		{"Zero Division", "1/0"},
		{"Invalid Input", "abc"},
		{"None Value", ""},
		{"Empty String", ""},
	}

	for _, tc := range testCasesError {
		t.Run(fmt.Sprintf("CreateIssue(%s, %s)", tc.title, tc.description), func(t *testing.T) {
			err := scrum11.CreateIssue(tc.title, tc.description)
			if err == nil {
				t.Errorf("CreateIssue(%s, %s) should have failed but did not", tc.title, tc.description)
			}
		})
	}
}