package main

import (
	"fmt"
	"io/ioutil"
	"net/http"
)

// JiraClient representa a interface para interagir com Jira
type JiraClient struct {
	URL    string
	Token  string
}

// GetIssues retrieves issues from Jira
func (j *JiraClient) GetIssues() ([]Issue, error) {
	req, err := http.NewRequest("GET", j.URL+"/rest/api/2/search?jql=project=YOUR_PROJECT&fields=id,status,name", nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %v", err)
	}
	req.Header.Set("Authorization", "Bearer "+j.Token)

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to send request: %v", err)
	}
	defer resp.Body.Close()

	body, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response body: %v", err)
	}

	var issues []Issue
	err = json.Unmarshal(body, &issues)
	if err != nil {
		return nil, fmt.Errorf("failed to parse JSON response: %v", err)
	}

	return issues, nil
}

// Issue represents a single issue in Jira
type Issue struct {
	ID   string `json:"id"`
	Status string `json:"status"`
	Name  string `json:"name"`
}

func main() {
	client := &JiraClient{
		URL:    "https://your-jira-instance.atlassian.net",
		Token:  "YOUR_JIRA_TOKEN",
	}

	issues, err := client.GetIssues()
	if err != nil {
		fmt.Println("Error:", err)
		return
	}

	for _, issue := range issues {
		fmt.Printf("Issue ID: %s, Status: %s, Name: %s\n", issue.ID, issue.Status, issue.Name)
	}
}