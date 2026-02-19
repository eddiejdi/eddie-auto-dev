import com.atlassian.jira.rest.client.api.JiraRestClient;
import com.atlassian.jira.rest.client.auth.BasicHttpAuthenticationHandler;
import com.atlassian.jira.rest.client.service.ProjectService;
import com.atlassian.jira.rest.client.service.UserProjectAssociationService;
import com.atlassian.jira.rest.client.util.RestClientBuilder;

import java.io.IOException;

public class JavaAgentJiraIntegration {

    public static void main(String[] args) {
        // Configuração do Jira Rest Client
        String jiraUrl = "https://your-jira-instance.com";
        String username = "your-username";
        String password = "your-password";

        BasicHttpAuthenticationHandler authenticationHandler = new BasicHttpAuthenticationHandler(username, password);
        RestClientBuilder builder = new RestClientBuilder(jiraUrl).setHttpClient(authenticationHandler);

        try (JiraRestClient client = builder.build()) {
            ProjectService projectService = client.getProjectService();
            UserProjectAssociationService userProjectAssociationService = client.getUserProjectAssociationService();

            // Exemplo de uso: Adicionar um usuário a uma projeto
            String projectId = "your-project-id";
            String usernameToAdd = "user-to-add";

            try {
                userProjectAssociationService.addUserToProject(projectId, usernameToAdd);
                System.out.println("Usuário adicionado ao projeto com sucesso.");
            } catch (IOException e) {
                System.err.println("Erro ao adicionar usuário ao projeto: " + e.getMessage());
            }
        } catch (IOException e) {
            System.err.println("Erro ao criar o Jira Rest Client: " + e.getMessage());
        }
    }
}