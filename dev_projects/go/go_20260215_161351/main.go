package main

import (
	"fmt"
	"log"

	"github.com/go-jira/jira/v4"
)

// JiraClient represents a client for interacting with the Jira API
type JiraClient struct {
	client *jira.Client
}

// NewJiraClient creates a new instance of JiraClient
func NewJiraClient(url, token string) (*JiraClient, error) {
	config := jira.Config{
		ServerURL: url,
		UserName:  "your_jira_username",
		Password:  token,
	}
	client, err := jira.New(config)
	if err != nil {
		return nil, fmt.Errorf("failed to create Jira client: %w", err)
	}
	return &JiraClient{client}, nil
}

// CreateIssue creates a new issue in Jira
func (jc *JiraClient) CreateIssue(summary, description string) (*jira.Issue, error) {
	issue := &jira.Issue{
		Summary: summary,
		Description: description,
	}
	issue, err := jc.client.CreateIssue(issue)
	if err != nil {
		return nil, fmt.Errorf("failed to create issue: %w", err)
	}
	return issue, nil
}

// main is the entry point of the program
func main() {
	url := "https://your-jira-instance.atlassian.net"
	token := "your-jira-token"

	jc, err := NewJiraClient(url, token)
	if err != nil {
		log.Fatalf("Failed to create Jira client: %v", err)
	}

	summary := "New feature request"
	description := "Implement a new feature in the application."

	issue, err := jc.CreateIssue(summary, description)
	if err != nil {
		log.Fatalf("Failed to create issue: %v", err)
	}

	fmt.Printf("Created issue with ID: %s\n", issue.ID)
}