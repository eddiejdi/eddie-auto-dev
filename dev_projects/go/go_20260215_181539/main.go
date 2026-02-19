package main

import (
	"fmt"
	"io/ioutil"
	"net/http"
	"os"
)

// JiraClient é uma interface para a API do Jira
type JiraClient interface {
	CreateIssue(title, description string) error
	GetIssues() ([]Issue, error)
}

// Issue representa um problema ou tarefa no Jira
type Issue struct {
	ID    string `json:"id"`
	Title string `json:"title"`
	Body  string `json:"body"`
}

// JiraAPI é uma implementação da interface JiraClient para a API do Jira
type JiraAPI struct{}

func (j *JiraAPI) CreateIssue(title, description string) error {
	url := "https://your-jira-instance.atlassian.net/rest/api/2/issue"
	reqBody := fmt.Sprintf(`{
		"fields": {
			"title": "%s",
			"description": "%s"
		}
	}`, title, description)

	resp, err := http.Post(url, "application/json", strings.NewReader(reqBody))
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != 201 {
		return fmt.Errorf("failed to create issue: %s", resp.Status)
	}

	return nil
}

func (j *JiraAPI) GetIssues() ([]Issue, error) {
	url := "https://your-jira-instance.atlassian.net/rest/api/2/search"
	reqBody := `{
		"jql": "project = YOUR_PROJECT",
		"fields": ["id", "title", "body"]
	}`

	resp, err := http.Post(url, "application/json", strings.NewReader(reqBody))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var issues []Issue
	err = json.NewDecoder(resp.Body).Decode(&issues)
	if err != nil {
		return nil, err
	}

	return issues, nil
}

func main() {
	jira := &JiraAPI{}

	title := "Test Issue"
	description := "This is a test issue created by the Go Agent."

	err := jira.CreateIssue(title, description)
	if err != nil {
		fmt.Println("Error creating issue:", err)
		return
	}

	fmt.Println("Issue created successfully.")

	issues, err := jira.GetIssues()
	if err != nil {
		fmt.Println("Error getting issues:", err)
		return
	}

	for _, issue := range issues {
		fmt.Printf("ID: %s, Title: %s\n", issue.ID, issue.Title)
	}
}