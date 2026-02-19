package main

import (
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
)

// JiraAPI represents the API for interacting with Jira.
type JiraAPI struct {
	baseURL string
	token   string
}

// NewJiraAPI creates a new instance of JiraAPI.
func NewJiraAPI(baseURL, token string) *JiraAPI {
	return &JiraAPI{
		baseURL: baseURL,
		token:   token,
	}
}

// CreateIssue creates a new issue in Jira.
func (j *JiraAPI) CreateIssue(title, description string) (*http.Response, error) {
	url := fmt.Sprintf("%s/rest/api/2/issue", j.baseURL)
	req, err := http.NewRequest("POST", url, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", j.token))

	body := fmt.Sprintf(`{
		"fields": {
			"title": "%s",
			"description": "%s"
		}
	}`, title, description)

	req.Body = ioutil.NopCloser(strings.NewReader(body))
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	return resp, nil
}

// main is the entry point of the program.
func main() {
	jiraAPI := NewJiraAPI("https://your-jira-instance.atlassian.net", "your-api-token")

	title := "New Test Issue"
	description := "This is a test issue created using Go Agent and Jira API."

	resp, err := jiraAPI.CreateIssue(title, description)
	if err != nil {
		log.Fatalf("Failed to create issue: %v", err)
	}
	fmt.Printf("Response status code: %d\n", resp.StatusCode)

	// You can add more functionality here if needed
}