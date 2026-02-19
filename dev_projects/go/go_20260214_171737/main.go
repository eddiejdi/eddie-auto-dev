package main

import (
	"fmt"
	"log"

	"github.com/go-jira/jira/v4"
)

// JiraClient represents a client to interact with Jira API
type JiraClient struct {
	client *jira.Client
}

// NewJiraClient creates a new instance of JiraClient
func NewJiraClient(url, token string) (*JiraClient, error) {
	client, err := jira.NewClient(url, token)
	if err != nil {
		return nil, fmt.Errorf("failed to create Jira client: %v", err)
	}
	return &JiraClient{client: client}, nil
}

// CreateIssue creates a new issue in Jira
func (jc *JiraClient) CreateIssue(summary string, description string) (*jira.Issue, error) {
	projectKey := "YOUR_PROJECT_KEY" // Replace with your project key
	issueType := "Bug"              // Replace with your issue type

	fields := map[string]interface{}{
		"summary": summary,
		"description": description,
	}

	createIssueRequest := jira.CreateIssueRequest{
	 Fields: fields,
	}

	newIssue, err := jc.client.Issues.Create(projectKey, createIssueRequest)
	if err != nil {
		return nil, fmt.Errorf("failed to create issue: %v", err)
	}
	return newIssue, nil
}

// main is the entry point of the application
func main() {
	url := "https://your-jira-instance.atlassian.net"
	token := "YOUR_JIRA_TOKEN"

	jc, err := NewJiraClient(url, token)
	if err != nil {
		log.Fatalf("Failed to create Jira client: %v", err)
	}

	summary := "New feature request"
	description := "Implement a new feature that allows users to search for products."

	newIssue, err := jc.CreateIssue(summary, description)
	if err != nil {
		log.Fatalf("Failed to create issue: %v", err)
	}

	fmt.Printf("Created issue with ID: %s\n", newIssue.ID)
}