package main

import (
	"fmt"
	"net/http"
)

// JiraClient é uma estrutura para representar a conexão com o Jira API
type JiraClient struct {
	baseURL string
	token   string
}

// NewJiraClient cria um novo cliente de Jira
func NewJiraClient(baseURL, token string) *JiraClient {
	return &JiraClient{
		baseURL: baseURL,
		token:   token,
	}
}

// GetIssues realiza uma requisição GET para obter issues do Jira
func (j *JiraClient) GetIssues(query string) ([]map[string]interface{}, error) {
	url := fmt.Sprintf("%s/rest/api/2/search?jql=%s", j.baseURL, query)
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+j.token)

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var issues []map[string]interface{}
	err = json.NewDecoder(resp.Body).Decode(&issues)
	if err != nil {
		return nil, err
	}

	return issues, nil
}

// main é a função principal do programa
func main() {
	client := NewJiraClient("https://your-jira-instance.atlassian.net", "your-api-token")

	query := "project=YOUR_PROJECT AND status IN (OPEN, IN_PROGRESS)"
	issues, err := client.GetIssues(query)
	if err != nil {
		fmt.Println("Error fetching issues:", err)
		return
	}

	for _, issue := range issues {
		fmt.Printf("Issue ID: %s\n", issue["id"])
		fmt.Printf("Summary: %s\n", issue["fields"].(map[string]interface{})["summary"])
		fmt.Printf("Status: %s\n", issue["fields"].(map[string]interface{})["status"].(string))
		fmt.Println()
	}
}