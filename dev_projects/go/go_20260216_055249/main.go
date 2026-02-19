package main

import (
	"fmt"
	"io/ioutil"
	"net/http"
)

// JiraClient é uma struct que representa a conexão com o Jira API
type JiraClient struct {
	url    string
	token  string
	client *http.Client
}

// NewJiraClient cria um novo cliente de Jira
func NewJiraClient(url, token string) *JiraClient {
	return &JiraClient{
		url:    url,
		token:  token,
		client: &http.Client{},
	}
}

// GetIssue busca uma issue no Jira pelo ID
func (j *JiraClient) GetIssue(issueID string) (*http.Response, error) {
	req, err := http.NewRequest("GET", j.url+"/rest/api/2/issue/"+issueID, nil)
	if err != nil {
		return nil, err
	}

	req.Header.Set("Authorization", "Basic "+j.token)
	req.Header.Set("Content-Type", "application/json")

	return j.client.Do(req)
}

// UpdateIssue atualiza uma issue no Jira
func (j *JiraClient) UpdateIssue(issueID string, updatePayload string) (*http.Response, error) {
	req, err := http.NewRequest("PUT", j.url+"/rest/api/2/issue/"+issueID, strings.NewReader(updatePayload))
	if err != nil {
		return nil, err
	}

	req.Header.Set("Authorization", "Basic "+j.token)
	req.Header.Set("Content-Type", "application/json")

	return j.client.Do(req)
}

// main é a função principal do programa
func main() {
	url := "https://your-jira-instance.atlassian.net"
	token := "your-api-token"

	jiraClient := NewJiraClient(url, token)

	issueID := "ABC-123"
	updatePayload := `{
		"fields": {
			"description": "Updated issue description",
			"status": {
				"name": "In Progress"
			}
		}
	}`

	resp, err := jiraClient.UpdateIssue(issueID, updatePayload)
	if err != nil {
		fmt.Println("Error updating issue:", err)
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