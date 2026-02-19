package main

import (
	"fmt"
	"log"
	"net/http"
)

// JiraAPI represents the API to interact with Jira
type JiraAPI struct {
	BaseURL string
}

// CreateJiraAPIClient initializes a new instance of JiraAPI
func CreateJiraAPIClient(baseURL string) *JiraAPI {
	return &JiraAPI{
		BaseURL: baseURL,
	}
}

// GetIssue retrieves an issue from Jira by its ID
func (j *JiraAPI) GetIssue(issueID string) (*http.Response, error) {
	url := fmt.Sprintf("%s/rest/api/2/issue/%s", j.BaseURL, issueID)
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, err
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, err
	}
	return resp, nil
}

// UpdateIssue updates an issue in Jira by its ID
func (j *JiraAPI) UpdateIssue(issueID string, payload map[string]interface{}) (*http.Response, error) {
	url := fmt.Sprintf("%s/rest/api/2/issue/%s", j.BaseURL, issueID)
	req, err := http.NewRequest("PUT", url, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	jsonPayload, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}
	req.Body = ioutil.NopCloser(bytes.NewBuffer(jsonPayload))
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, err
	}
	return resp, nil
}

// Example usage of the JiraAPI
func main() {
	jira := CreateJiraAPIClient("https://your-jira-instance.atlassian.net")

	issueID := "12345"
	payload := map[string]interface{}{
		"fields": map[string]interface{}{
			"description": "Updated issue description",
		},
	}

	resp, err := jira.UpdateIssue(issueID, payload)
	if err != nil {
		log.Fatalf("Failed to update issue: %v", err)
	}
	defer resp.Body.Close()

	fmt.Println("Response status:", resp.Status)
}