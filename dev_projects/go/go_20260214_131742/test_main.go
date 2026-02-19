package main

import (
	"net/http"
	"testing"
)

func TestJiraClient_CreateIssue(t *testing.T) {
	jiraClient := &JiraAPI{}

	testCases := []struct {
		title    string
		description string
		expected error
	}{
		{"New Issue", "This is a new issue.", nil},
		{"Invalid Title", "", fmt.Errorf("Title cannot be empty")},
		{"Empty Description", "New issue", fmt.Errorf("Description cannot be empty")},
	}

	for _, tc := range testCases {
		err := jiraClient.CreateIssue(tc.title, tc.description)
		if err != tc.expected {
			t.Errorf("CreateIssue(%q, %q) = %v; want %v", tc.title, tc.description, err, tc.expected)
		}
	}
}

func TestGoAgentClient_ScheduleJob(t *testing.T) {
	goAgentClient := &GoAgentAPI{}

	testCases := []struct {
		jobName string
		expected error
	}{
		{"New Job", nil},
		{"Invalid Job Name", fmt.Errorf("Job name cannot be empty")},
	}

	for _, tc := range testCases {
		err := goAgentClient.ScheduleJob(tc.jobName)
		if err != tc.expected {
			t.Errorf("ScheduleJob(%q) = %v; want %v", tc.jobName, err, tc.expected)
		}
	}
}