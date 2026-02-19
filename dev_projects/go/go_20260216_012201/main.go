package main

import (
	"fmt"
	"net/http"
)

// JiraClient é a interface para interagir com o servidor Jira
type JiraClient interface {
	CreateIssue(title, description string) error
}

// GoAgentClient é a interface para interagir com o Go Agent
type GoAgentClient interface {
	RunTest(testName string) error
}

// Scrum11Agent é a classe principal do agente Scrum-11
type Scrum11Agent struct {
	jiraClient JiraClient
	goAgentClient GoAgentClient
}

// NewScrum11Agent cria uma nova instância de Scrum11Agent
func NewScrum11Agent(jiraClient, goAgentClient JiraClient) *Scrum11Agent {
	return &Scrum11Agent{jiraClient, goAgentClient}
}

// CreateIssue envia um novo issue para o servidor Jira
func (s *Scrum11Agent) CreateIssue(title, description string) error {
	return s.jiraClient.CreateIssue(title, description)
}

// RunTest executa um teste no Go Agent
func (s *Scrum11Agent) RunTest(testName string) error {
	return s.goAgentClient.RunTest(testName)
}

// Main é a função principal do programa
func main() {
	// Simulação de criação de issue no Jira
	jiraClient := &JiraClientMock{}
	goAgentClient := &GoAgentClientMock{}

	scrum11Agent := NewScrum11Agent(jiraClient, goAgentClient)

	err := scrum11Agent.CreateIssue("Teste Scrum-11", "Execução do teste Scrum-11")
	if err != nil {
		fmt.Println("Erro ao criar issue:", err)
		return
	}

	err = scrum11Agent.RunTest("Teste Go Agent")
	if err != nil {
		fmt.Println("Erro ao executar teste:", err)
		return
	}
}

// JiraClientMock é uma implementação de JiraClient para simulação
type JiraClientMock struct{}

func (m *JiraClientMock) CreateIssue(title, description string) error {
	fmt.Printf("Criando issue: %s - %s\n", title, description)
	return nil
}

// GoAgentClientMock é uma implementação de GoAgentClient para simulação
type GoAgentClientMock struct{}

func (m *GoAgentClientMock) RunTest(testName string) error {
	fmt.Printf("Executando teste: %s\n", testName)
	return nil
}