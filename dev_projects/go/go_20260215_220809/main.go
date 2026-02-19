package main

import (
	"fmt"
	"io/ioutil"
	"net/http"
)

// JiraClient representa a API do Jira
type JiraClient struct {
	url   string
	token string
}

// NewJiraClient cria uma nova instância de JiraClient
func NewJiraClient(url, token string) *JiraClient {
	return &JiraClient{
		url:   url,
		token: token,
	}
}

// GetIssue retrieves an issue from Jira by its ID
func (j *JiraClient) GetIssue(issueID string) (*http.Response, error) {
	req, err := http.NewRequest("GET", j.url+"/rest/api/2/issue/"+issueID, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+j.token)
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}

	return resp, nil
}

// main is the entry point of the program
func main() {
	url := "https://your-jira-instance.atlassian.net"
	token := "your-jira-token"

	jira := NewJiraClient(url, token)

	issueID := "ABC-123"
	resp, err := jira.GetIssue(issueID)
	if err != nil {
		fmt.Println("Error retrieving issue:", err)
		return
	}
	defer resp.Body.Close()

	body, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		fmt.Println("Error reading response body:", err)
		return
	}

	fmt.Println(string(body))
}