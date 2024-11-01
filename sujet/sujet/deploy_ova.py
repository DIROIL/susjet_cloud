import json
import ssl
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim
import atexit

def get_datastore(content, datastore_name):
    """Retourne le datastore correspondant au nom donné."""
    for datastore in content.viewManager.CreateContainerView(content.rootFolder, [vim.Datastore], True).view:
        if datastore.name == datastore_name:
            return datastore
    raise ValueError(f"Datastore '{datastore_name}' not found.")

def get_resource_pool(content):
    """Retourne le premier resource pool disponible."""
    for resource_pool in content.viewManager.CreateContainerView(
        content.rootFolder, [vim.ResourcePool], True).view:
        return resource_pool
    raise ValueError("No resource pools found.")

def deploy_ova(si, ova_path, vm_name, num_cpus, memory_mb, datastore_name):
    content = si.RetrieveContent()
    ovf_manager = content.ovfManager

    # Lire le contenu de l'OVF
    with open(ova_path, 'r') as ovf_file:
        ovf_descriptor = ovf_file.read()

    # Obtenir le datastore spécifié
    datastore = get_datastore(content, datastore_name)

    # Obtenir le resource pool
    resource_pool = get_resource_pool(content)

    # Obtenir le dossier où la VM va être déployée
    vm_folder = content.rootFolder  # ou un autre dossier spécifique

    # Créer les spécifications d'importation
    import_spec_params = vim.OvfManager.CreateImportSpecParams()
    import_spec = ovf_manager.CreateImportSpec(ovf_descriptor, resource_pool, datastore, import_spec_params)

    # Vérifiez si des erreurs sont présentes dans l'import_spec
    if import_spec.error:
        print("Error in import spec:")
        for error in import_spec.error:
            print(error)
        return

    # Configuration des ressources de la machine virtuelle
    entity_config = import_spec.importSpec.entityConfig
    if hasattr(entity_config, 'deviceConfigSpec'):
        for device in entity_config.deviceConfigSpec:
            if isinstance(device, vim.vm.device.VirtualCPU):
                device.resourceAllocation = vim.ResourceAllocationInfo()
                device.resourceAllocation.limit = num_cpus
            elif isinstance(device, vim.vm.device.VirtualMemory):
                device.resourceAllocation = vim.ResourceAllocationInfo()
                device.resourceAllocation.limit = memory_mb

    # Déployer la machine virtuelle
    try:
        resource_pool.ImportVApp(import_spec.importSpec, vm_folder)
        print(f"{vm_name} is being deployed with {num_cpus} CPUs and {memory_mb} MB of memory. Check the vSphere client for status.")
    except Exception as e:
        print(f"Failed to initiate the import task: {str(e)}")

def main():
    # Charger la configuration
    with open('config.json') as f:
        config = json.load(f)

    # Connexion à l'hôte ESXi
    context = ssl._create_unverified_context()
    si = SmartConnect(host=config['esxi_host'], user=config['username'],
                      pwd=config['password'], sslContext=context)
    atexit.register(Disconnect, si)

    # Déployer les instances
    for i in range(config['instances']):
        vm_name = f"{config['vm_name']}-{i+1}"  # Correction de la syntaxe
        num_cpus = config['num_cpus']       # Nombre de CPU à attribuer
        memory_mb = config['memory_mb']     # Taille de la mémoire en Mo
        datastore_name = config['datastore'] # Nom du datastore
        deploy_ova(si, config['ova_path'], vm_name, num_cpus, memory_mb, datastore_name)

if __name__ == "__main__":
    main()