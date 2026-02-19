import com.atlassian.jira.component.ComponentManager;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.UserFieldManager;
import com.atlassian.jira.user.ApplicationUser;
import com.atlassian.jira.user.UserManager;

public class JavaAgent {

    public static void main(String[] args) {
        // Inicializa o ComponentManager
        ComponentManager componentManager = ComponentManager.getInstance();

        // Obtém as instâncias de outros serviços necessários
        FieldManager fieldManager = componentManager.getFieldManager();
        UserFieldManager userFieldManager = componentManager.getUserFieldManager();
        UserManager userManager = componentManager.getUserManager();

        // Exemplo de uso: Criar um novo usuário e associá-lo a um campo personalizado
        ApplicationUser user = userManager.createUser("newuser", "password");
        CustomFieldManager customFieldManager = componentManager.getCustomFieldManager();
        CustomField customField = customFieldManager.getCustomFieldByName("My Personal Field");

        if (customField != null) {
            try {
                fieldManager.updateIssue(user, "issue123", new HashMap<String, Object>() {{
                    put(customField.getName(), "New Value");
                }});
                System.out.println("User updated successfully.");
            } catch (Exception e) {
                System.err.println("Error updating user: " + e.getMessage());
            }
        } else {
            System.err.println("Custom field not found.");
        }
    }
}