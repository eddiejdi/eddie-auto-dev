package main

import (
	"testing"
)

// TestCreateIssue tests the CreateIssue method of the Integrator struct
func TestCreateIssue(t *testing.T) {
	integrator := &Integrator{}

	testCases := []struct {
		title     string
		description string
		expected error
	}{
		{"Test Issue", "This is a test issue for integration.", nil},
		// Add more test cases as needed
	}

	for _, tc := range testCases {
		t.Run(fmt.Sprintf("CreateIssue(%s, %s)", tc.title, tc.description), func(t *testing.T) {
			err := integrator.CreateIssue(tc.title, tc.description)
			if err != tc.expected {
				t.Errorf("CreateIssue(%s, %s) = %v; want %v", tc.title, tc.description, err, tc.expected)
			}
		})
	}
}

// TestSendEvent tests the SendEvent method of the Integrator struct
func TestSendEvent(t *testing.T) {
	integrator := &Integrator{}

	testCases := []struct {
		eventName string
		eventData map[string]interface{}
		expected error
	}{
		{"create_issue", map[string]interface{}{"issueTitle": "Test Issue", "description": "This is a test issue for integration."}, nil},
		// Add more test cases as needed
	}

	for _, tc := range testCases {
		t.Run(fmt.Sprintf("SendEvent(%s, %v)", tc.eventName, tc.eventData), func(t *testing.T) {
			err := integrator.SendEvent(tc.eventName, tc.eventData)
			if err != tc.expected {
				t.Errorf("SendEvent(%s, %v) = %v; want %v", tc.eventName, tc.eventData, err, tc.expected)
			}
		})
	}
}