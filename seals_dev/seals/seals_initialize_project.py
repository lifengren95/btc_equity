# initialize_project defines the run() command for the whole project, which takes the project object as its only function.

import hazelbean as hb
# conda_envs_with_cython = hb.check_which_conda_envs_have_library_installed('cython')
# print(conda_envs_with_cython)


import os, sys
import hazelbean as hb
from hazelbean import cloud_utils
import pandas as pd

import seals_main
import seals_utils
import seals_generate_base_data
import seals_process_coarse_timeseries
import seals_visualization_tasks
import config
from seals_utils import download_google_cloud_blob
import seals_tasks


def set_advanced_options(p):       
    
    p.build_overviews_and_stats = 0  # For later fast-viewing, this can be enabled to write ovr files and geotiff stats files. NYI anywhere.
    p.force_to_global_bb = 0
    p.plotting_level = 0 

    p.cython_reporting_level = 0
    p.calibration_cython_reporting_level = 0
    p.output_writing_level = 0  # >=2 writes chunk-baseline lulc
    p.write_projected_coarse_change_chunks = 0  # in the SEALS allocation, for troubleshooting, it can be useful to see what was the coarse allocation input.
    p.write_calibration_generation_arrays = 0  # in the SEALS allocation, for troubleshooting, it can be useful to see what was the coarse allocation input.

    p.years_to_convolve_override = None # Because convolving a lulc map is so computationally expensive, you may set this option to manually set which year of convolutions to use. If this is None (the default), it will convolve the base year.

    p.num_workers = None  # None sets it to max available. Otherwise, set to an integer.

    # Determine if overviews should be written.
    p.write_global_lulc_overviews_and_tifs = True    

    # Specifies which sigmas should be used in a gaussian blur of the class-presence tifs in order to regress on adjacency.
    # Note this will have a huge impact on performance as full-extent gaussian blurs for each class will be generated for
    # each sigma.
    # TODOO Figure out how this relates to the coefficients csv. I could probably derive these values from that csv.
    p.gaussian_sigmas_to_test = [1, 5]

    # There are still multiple ways to do the allocation. Unless we input a fully-defined
    # change matrix, there will always be ambiguities. One way of lessening them is to 
    # switch from the default allocation method (just do positive allocation requests)
    # to one that also increases the total goal when some other class
    # goes on it. Allowing it leads to a greater amount of the requested allocation
    # happening, but it can lead to funnylooking total-flip cells.
    p.allow_contracting = 0

    # Change how many generations of training to allow. A generation is an exhaustive search so relatievely few generations are required to get to a point
    # where no more improvements can be found.
    p.num_generations = 1

    # If True, will load that which was calculated in the calibration run.
    p.use_calibration_created_coefficients = 0

    
    # Sometimes runs fail mid run. This checks for that and picks up where there is a completed file for that zone. 
    # However doing so can cause confusing cache-invalidation situations for troubleshooting so it's off by default.
    p.skip_created_downscaling_zones = 0

    # For testing,it may be useful to just run the first element of each iterator for speed.
    p.run_only_first_element_of_each_iterator = 0



    # On the stitched_lulc_simplified_scenarios task, optionally clip it to the aoi. Be aware that this
    # means you can no longer user it in Pyramid-style operations (basically all besides zonal stats).
    p.clip_to_aoi = 1
    
    ### ------------------- SET UNUSED ATTRIBUTES TO NONE ------------------- ###
    
    if not hasattr(p, 'subset_of_blocks_to_run'):
        p.subset_of_blocks_to_run = None # No subset


def initialize_scenario_definitions(p):
    
    # If the scenarios csv doesn't exist, generate it and put it in the input_dir 
    if not hb.path_exists(p.scenario_definitions_path):
        
        # Before generating a new scenarios file, check if there's not one in the base data with the matching name.
        possible_path = p.get_path('seals', 'default_inputs', p.scenario_definitions_filename)
        if hb.path_exists(possible_path):
            hb.path_copy(possible_path, p.scenario_definitions_path)
            
        # If theres truly nothing in the base data, generate it for the default.
        else:        
            # There are multiple scenario_csv generator functions. Here we use the default.
            seals_utils.set_attributes_to_dynamic_default(p) # Default option

            # Once the attributes are set, generate the scenarios csv and put it in the input_dir.
            seals_utils.generate_scenarios_csv_and_put_in_input_dir(p)
        
        # After writing, read it it back in, cause this is how other attributes might be modified
        p.scenarios_df = pd.read_csv(p.scenario_definitions_path)
    else:
        # Read in the scenarios csv and assign the first row to the attributes of this object (in order to setup additional 
        # project attributes like the resolutions of the fine scale and coarse scale data)
        p.scenarios_df = pd.read_csv(p.scenario_definitions_path)

    # Set p attributes from df (but only the first row, cause its for initialization)
    for index, row in p.scenarios_df.iterrows():
        
        # NOTE! This also downloads any files references in the csv
        seals_utils.assign_df_row_to_object_attributes(p, row)
        break # Just get first for initialization.

    # calibration_parameters_override_dict can be used in specific scenarios to e.g., not allow expansion of cropland into forest by overwriting the default calibration. Note that I haven't set exactly how this
    # will work if it is specific to certain zones or a single-zone that overrides all. The latter would probably be easier.
    # If the DF has a value, override. If it is None or "", keep from parameters source.
    p.calibration_parameters_override_dict = {}
    # p.calibration_parameters_override_dict['rcp45_ssp2'][2030]['BAU'] = os.path.join(p.input_dir, 'calibration_overrides', 'prevent_cropland_expansion_into_forest.xlsx')

    
    
    # Some variables need further processing into attributes, like parsing a correspondence csv into a dict.
    seals_utils.set_derived_attributes(p)


def build_task_tree_by_name(p, task_tree_name):
    full_task_tree_name = 'build_' + task_tree_name + '_task_tree'
    target_function = globals()[full_task_tree_name]
    print('Launching SEALS. Building task tree: ' + task_tree_name)

    target_function(p)

# def build_simple_allocation_run_task_tree(p):
#     # This is the default task tree that is run on a new seals installation.

#     ##### Preprocessing #####

#     # Define the project AOI
#     p.project_aoi_task = p.add_task(project_aoi)

#     # Download the base data (note that it saves to p.base_data_dir and thus doesn't create its own dir)
#     p.base_data_task = p.add_task(seals_process_coarse_timeseries.download_base_data, creates_dir=False)


#     ##### FINE PROCESSED INPUTS #####

#     # Make folder for all generated data.
#     p.fine_processed_inputs_task = p.add_task(seals_generate_base_data.fine_processed_inputs)

#     # Generate some simple gaussian kernels for later convolutions
#     p.generated_kernels_task = p.add_task(seals_generate_base_data.generated_kernels, parent=p.fine_processed_inputs_task, creates_dir=False)

#     # Clip the fine LULC to the project AOI
#     p.lulc_clip_task = p.add_task(seals_generate_base_data.lulc_clip, parent=p.fine_processed_inputs_task, creates_dir=False)

#     # Simplify the LULC
#     p.lulc_simplifications_task = p.add_task(seals_generate_base_data.lulc_simplifications, parent=p.fine_processed_inputs_task, creates_dir=False)

#     # Convert the simplified LULC into 1 binary presence map for each simplified LUC
#     p.lulc_binaries_task = p.add_task(seals_generate_base_data.lulc_binaries, parent=p.fine_processed_inputs_task, creates_dir=False)

#     # Convolve the lulc_binaries # TODOO Precache this for performance
#     p.lulc_convolutions_task = p.add_task(seals_generate_base_data.lulc_convolutions, parent=p.fine_processed_inputs_task, creates_dir=False)

#     # # Write a LOCAL version of the regression starting values based on the new data generated.
#     # p.local_data_regression_starting_values_task = p.add_task(seals_generate_base_data.local_data_regressors_starting_values)


#     ##### COARSE CHANGE #####
#     # Make folder for all generated data.
#     p.coarse_change_task = p.add_task(seals_process_coarse_timeseries.coarse_change, skip_existing=0)

#     # Extract coarse change from source
#     p.extraction_task = p.add_task(seals_process_coarse_timeseries.coarse_extraction, parent=p.coarse_change_task, run=1, skip_existing=0)

#     # Reclassify coarse source to simplified scheme 
#     p.coarse_simplified_task = p.add_task(seals_process_coarse_timeseries.coarse_simplified_proportion, parent=p.coarse_change_task, skip_existing=0)

#     # Calculate LUH2_simplified difference from base year
#     p.coarse_simplified_ha_difference_from_base_year_task = p.add_task(seals_process_coarse_timeseries.coarse_simplified_ha_difference_from_base_year, parent=p.coarse_change_task, skip_existing=0)


#     ##### ALLOCATION #####

#     # Iterate through different scenarios to be allocated.
#     p.allocations_task = p.add_iterator(seals_main.allocations, run_in_parallel=0, skip_existing=0)

#     # Define the zones overwhich parallel allocation should be run
#     p.allocation_zones_task = p.add_iterator(seals_main.allocation_zones, parent=p.allocations_task, run_in_parallel=p.run_in_parallel, skip_existing=0)

#     # Actually do the allocation
#     p.allocation_task = p.add_task(seals_main.allocation, parent=p.allocation_zones_task, skip_existing=1)



#     ##### STITCH ZONES #####

#     # Stitch the simplified LULC tiles back together
#     p.stitched_lulc_simplified_scenarios_task = p.add_task(seals_main.stitched_lulc_simplified_scenarios)

#     # # Reclassify the stitched simplified to original classification.
#     # p.stitched_lulc_esa_scenarios_task =  p.add_task(seals_main.stitched_lulc_esa_scenarios)

#     # p.post_run_visualization_task = p.add_task(seals_visualization_tasks.post_run_visualization)


def build_allocation_run_task_tree(p):
    # This is the default task tree that is run on a new seals installation.

    ##### Preprocessing #####

    # Define the project AOI
    p.project_aoi_task = p.add_task(project_aoi)

    # Download the base data (note that it saves to p.base_data_dir and thus doesn't create its own dir)
    p.base_data_task = p.add_task(seals_process_coarse_timeseries.download_base_data, creates_dir=False)


    ##### FINE PROCESSED INPUTS #####

    # Make folder for all generated data.
    p.fine_processed_inputs_task = p.add_task(seals_generate_base_data.fine_processed_inputs)

    # Generate some simple gaussian kernels for later convolutions
    p.generated_kernels_task = p.add_task(seals_generate_base_data.generated_kernels, parent=p.fine_processed_inputs_task, creates_dir=False)

    # Clip the fine LULC to the project AOI
    p.lulc_clip_task = p.add_task(seals_generate_base_data.lulc_clip, parent=p.fine_processed_inputs_task, creates_dir=False)

    # Simplify the LULC
    p.lulc_simplifications_task = p.add_task(seals_generate_base_data.lulc_simplifications, parent=p.fine_processed_inputs_task, creates_dir=False)

    # Convert the simplified LULC into 1 binary presence map for each simplified LUC
    p.lulc_binaries_task = p.add_task(seals_generate_base_data.lulc_binaries, parent=p.fine_processed_inputs_task, creates_dir=False)

    # Convolve the lulc_binaries # TODOO Precache this for performance
    p.lulc_convolutions_task = p.add_task(seals_generate_base_data.lulc_convolutions, parent=p.fine_processed_inputs_task, creates_dir=False)

    # # Write a LOCAL version of the regression starting values based on the new data generated.
    # p.local_data_regression_starting_values_task = p.add_task(seals_generate_base_data.local_data_regressors_starting_values)


    ##### COARSE CHANGE #####
    # Make folder for all generated data.
    p.coarse_change_task = p.add_task(seals_process_coarse_timeseries.coarse_change, skip_existing=0)

    # Extract coarse change from source
    p.extraction_task = p.add_task(seals_process_coarse_timeseries.coarse_extraction, parent=p.coarse_change_task, run=1, skip_existing=0)

    # Reclassify coarse source to simplified scheme 
    p.coarse_simplified_task = p.add_task(seals_process_coarse_timeseries.coarse_simplified_proportion, parent=p.coarse_change_task, skip_existing=0)

    # Calculate LUH2_simplified difference from base year
    p.coarse_simplified_ha_difference_from_previous_year_task = p.add_task(seals_process_coarse_timeseries.coarse_simplified_ha_difference_from_previous_year, parent=p.coarse_change_task, skip_existing=0)


    ##### ALLOCATION #####

    # Iterate through different scenarios to be allocated.
    p.allocations_task = p.add_iterator(seals_main.allocations, run_in_parallel=0, skip_existing=0)

    # Define the zones overwhich parallel allocation should be run
    p.allocation_zones_task = p.add_iterator(seals_main.allocation_zones, parent=p.allocations_task, run_in_parallel=p.run_in_parallel, skip_existing=0)

    # Actually do the allocation
    p.allocation_task = p.add_task(seals_main.allocation, parent=p.allocation_zones_task, skip_existing=1)



    ##### STITCH ZONES #####

    # Stitch the simplified LULC tiles back together
    p.stitched_lulc_simplified_scenarios_task = p.add_task(seals_main.stitched_lulc_simplified_scenarios)

    # # Reclassify the stitched simplified to original classification.
    # p.stitched_lulc_esa_scenarios_task =  p.add_task(seals_main.stitched_lulc_esa_scenarios)

    # p.post_run_visualization_task = p.add_task(seals_visualization_tasks.post_run_visualization)


def build_visualization_task_tree(p):
    # This is the default task tree that is run on a new seals installation.

    ##### Preprocessing #####

    # Define the project AOI
    p.project_aoi_task = p.add_task(project_aoi)

    # Download the base data (note that it saves to p.base_data_dir and thus doesn't create its own dir)
    p.base_data_task = p.add_task(seals_process_coarse_timeseries.download_base_data, creates_dir=False, run=0)


    ##### FINE PROCESSED INPUTS #####

    # Make folder for all generated data.
    p.fine_processed_inputs_task = p.add_task(seals_generate_base_data.fine_processed_inputs, run=0)

    # Generate some simple gaussian kernels for later convolutions
    p.generated_kernels_task = p.add_task(seals_generate_base_data.generated_kernels, parent=p.fine_processed_inputs_task, creates_dir=False, run=0)

    # Clip the fine LULC to the project AOI
    p.lulc_clip_task = p.add_task(seals_generate_base_data.lulc_clip, parent=p.fine_processed_inputs_task, creates_dir=False, run=0)

    # Simplify the LULC
    p.lulc_simplifications_task = p.add_task(seals_generate_base_data.lulc_simplifications, parent=p.fine_processed_inputs_task, creates_dir=False, run=0)

    # Convert the simplified LULC into 1 binary presence map for each simplified LUC
    p.lulc_binaries_task = p.add_task(seals_generate_base_data.lulc_binaries, parent=p.fine_processed_inputs_task, creates_dir=False, run=0)

    # Convolve the lulc_binaries # TODOO Precache this for performance
    p.lulc_convolutions_task = p.add_task(seals_generate_base_data.lulc_convolutions, parent=p.fine_processed_inputs_task, creates_dir=False, run=0)

    # # Write a LOCAL version of the regression starting values based on the new data generated.
    # p.local_data_regression_starting_values_task = p.add_task(seals_generate_base_data.local_data_regressors_starting_values)


    ##### COARSE CHANGE #####
    # Make folder for all generated data.
    p.coarse_change_task = p.add_task(seals_process_coarse_timeseries.coarse_change, skip_existing=0, run=1)

    # Extract coarse change from source
    p.extraction_task = p.add_task(seals_process_coarse_timeseries.coarse_extraction, parent=p.coarse_change_task, skip_existing=0, run=0)

    # Reclassify coarse source to simplified scheme 
    p.coarse_simplified_task = p.add_task(seals_process_coarse_timeseries.coarse_simplified_proportion, parent=p.coarse_change_task, skip_existing=0, run=0)

    # Calculate LUH2_simplified difference from base year
    p.coarse_simplified_ha_difference_from_previous_year_task = p.add_task(seals_process_coarse_timeseries.coarse_simplified_ha_difference_from_previous_year, parent=p.coarse_change_task, skip_existing=0, run=0)


    ##### ALLOCATION #####

    # Iterate through different scenarios to be allocated.
    p.allocations_task = p.add_iterator(seals_main.allocations, run_in_parallel=0, skip_existing=0, run=0)

    # Define the zones overwhich parallel allocation should be run
    p.allocation_zones_task = p.add_iterator(seals_main.allocation_zones, parent=p.allocations_task, run_in_parallel=p.run_in_parallel, skip_existing=0, run=0)

    # Actually do the allocation
    p.allocation_task = p.add_task(seals_main.allocation, parent=p.allocation_zones_task, skip_existing=1, run=0)



    ##### STITCH ZONES #####

    # Stitch the simplified LULC tiles back together
    p.stitched_lulc_simplified_scenarios_task = p.add_task(seals_main.stitched_lulc_simplified_scenarios, run=0)

    # # Reclassify the stitched simplified to original classification.
    # p.stitched_lulc_esa_scenarios_task =  p.add_task(seals_main.stitched_lulc_esa_scenarios)

    # p.post_run_visualization_task = p.add_task(seals_visualization_tasks.post_run_visualization)


    ##### VIZUALIZE EXISTING DATA #####
    # Make folder for all visualizations.
    p.visualization_task = p.add_task(seals_visualization_tasks.visualization, skip_existing=0, run=1)

    # For each class, plot the coarse and fine data
    p.coarse_change_with_class_change_task = p.add_task(seals_visualization_tasks.coarse_change_with_class_change, parent=p.visualization_task, run=1)

    p.coarse_fine_with_report_task = p.add_task(seals_visualization_tasks.coarse_fine_with_report, parent=p.visualization_task, run=1)

    # For each class, plot the coarse and fine data
    p.create_full_change_matrices_task = p.add_task(seals_main.full_change_matrices, parent=p.visualization_task, run=1)
    
    # For each class, plot the coarse and fine data
    p.target_zones_matrices_task = p.add_task(seals_main.target_zones_matrices, parent=p.visualization_task, run=1)
    
    # For each class, plot the coarse and fine data
    p.plot_full_change_matrices_pngs_task = p.add_task(seals_visualization_tasks.full_change_matrices_pngs, parent=p.visualization_task, run=1)
    
    # For each class, plot the coarse and fine data
    p.plot_target_zones_matrices_pngs_task = p.add_task(seals_visualization_tasks.target_zones_matrices_pngs, parent=p.visualization_task, run=1)

    # Simple plot of the PNGs.
    p.lulc_pngs_task = p.add_task(seals_visualization_tasks.lulc_pngs, parent=p.visualization_task, run=1)

def build_allocation_and_visualization_run_task_tree(p):
    
    # Define the project AOI
    p.project_aoi_task = p.add_task(project_aoi)

    # Download the base data (note that it saves to p.base_data_dir and thus doesn't create its own dir)
    p.base_data_task = p.add_task(seals_process_coarse_timeseries.download_base_data, creates_dir=False)


    ##### FINE PROCESSED INPUTS #####

    # Make folder for all generated data.
    p.fine_processed_inputs_task = p.add_task(seals_generate_base_data.fine_processed_inputs)

    # Generate some simple gaussian kernels for later convolutions
    p.generated_kernels_task = p.add_task(seals_generate_base_data.generated_kernels, parent=p.fine_processed_inputs_task, creates_dir=False)

    # Clip the fine LULC to the project AOI
    p.lulc_clip_task = p.add_task(seals_generate_base_data.lulc_clip, parent=p.fine_processed_inputs_task, creates_dir=False)

    # Simplify the LULC
    p.lulc_simplifications_task = p.add_task(seals_generate_base_data.lulc_simplifications, parent=p.fine_processed_inputs_task, creates_dir=False)

    # Convert the simplified LULC into 1 binary presence map for each simplified LUC
    p.lulc_binaries_task = p.add_task(seals_generate_base_data.lulc_binaries, parent=p.fine_processed_inputs_task, creates_dir=False)

    # Convolve the lulc_binaries # TODOO Precache this for performance
    p.lulc_convolutions_task = p.add_task(seals_generate_base_data.lulc_convolutions, parent=p.fine_processed_inputs_task, creates_dir=False)

    # # Write a LOCAL version of the regression starting values based on the new data generated.
    # p.local_data_regression_starting_values_task = p.add_task(seals_generate_base_data.local_data_regressors_starting_values)


    ##### COARSE CHANGE #####
    # Make folder for all generated data.
    p.coarse_change_task = p.add_task(seals_process_coarse_timeseries.coarse_change, skip_existing=0)

    # Extract coarse change from source
    p.extraction_task = p.add_task(seals_process_coarse_timeseries.coarse_extraction, parent=p.coarse_change_task, run=1, skip_existing=0)

    # Reclassify coarse source to simplified scheme 
    p.coarse_simplified_task = p.add_task(seals_process_coarse_timeseries.coarse_simplified_proportion, parent=p.coarse_change_task, skip_existing=0)

    # Calculate LUH2_simplified difference from base year
    p.coarse_simplified_ha_difference_from_previous_year_task = p.add_task(seals_process_coarse_timeseries.coarse_simplified_ha_difference_from_previous_year, parent=p.coarse_change_task, skip_existing=0)


    ##### ALLOCATION #####

    # Iterate through different scenarios to be allocated.
    p.allocations_task = p.add_iterator(seals_main.allocations, run_in_parallel=0, skip_existing=0)

    # Define the zones overwhich parallel allocation should be run
    p.allocation_zones_task = p.add_iterator(seals_main.allocation_zones, parent=p.allocations_task, run_in_parallel=p.run_in_parallel, skip_existing=0)

    # Actually do the allocation
    p.allocation_task = p.add_task(seals_main.allocation, parent=p.allocation_zones_task, skip_existing=1)



    ##### STITCH ZONES #####

    # Stitch the simplified LULC tiles back together
    p.stitched_lulc_simplified_scenarios_task = p.add_task(seals_main.stitched_lulc_simplified_scenarios)

    # # Reclassify the stitched simplified to original classification.
    # p.stitched_lulc_esa_scenarios_task =  p.add_task(seals_main.stitched_lulc_esa_scenarios)

    # p.post_run_visualization_task = p.add_task(seals_visualization_tasks.post_run_visualization)

    ##### VIZUALIZE EXISTING DATA #####
    # Make folder for all visualizations.
    p.visualization_task = p.add_task(seals_visualization_tasks.visualization, skip_existing=0, run=1)

    # For each class, plot the coarse and fine data
    p.coarse_change_with_class_change_task = p.add_task(seals_visualization_tasks.coarse_change_with_class_change, parent=p.visualization_task, run=1)

    p.coarse_fine_with_report_task = p.add_task(seals_visualization_tasks.coarse_fine_with_report, parent=p.visualization_task, run=1)

    # For each class, plot the coarse and fine data
    p.create_full_change_matrices_task = p.add_task(seals_main.full_change_matrices, parent=p.visualization_task, run=1)
    
    # For each class, plot the coarse and fine data
    p.target_zones_matrices_task = p.add_task(seals_main.target_zones_matrices, parent=p.visualization_task, run=1)
    
    # For each class, plot the coarse and fine data
    p.plot_full_change_matrices_pngs_task = p.add_task(seals_visualization_tasks.full_change_matrices_pngs, parent=p.visualization_task, run=1)
    
    # For each class, plot the coarse and fine data
    # p.plot_target_zones_matrices_pngs_task = p.add_task(seals_visualization_tasks.target_zones_matrices_pngs, parent=p.visualization_task, run=1)

    # Simple plot of the PNGs.
    p.lulc_pngs_task = p.add_task(seals_visualization_tasks.lulc_pngs, parent=p.visualization_task, run=1)


def build_allocation_and_quick_visualization_run_task_tree(p):
    # This is the old default task tree that is run on a new seals installation.

    ##### Preprocessing #####

    # Define the project AOI
    p.project_aoi_task = p.add_task(project_aoi)

    # Download the base data (note that it saves to p.base_data_dir and thus doesn't create its own dir)
    p.base_data_task = p.add_task(seals_process_coarse_timeseries.download_base_data, creates_dir=False)


    ##### FINE PROCESSED INPUTS #####

    # Make folder for all generated data.
    p.fine_processed_inputs_task = p.add_task(seals_generate_base_data.fine_processed_inputs)

    # Generate some simple gaussian kernels for later convolutions
    p.generated_kernels_task = p.add_task(seals_generate_base_data.generated_kernels, parent=p.fine_processed_inputs_task, creates_dir=False)

    # Clip the fine LULC to the project AOI
    p.lulc_clip_task = p.add_task(seals_generate_base_data.lulc_clip, parent=p.fine_processed_inputs_task, creates_dir=False)

    # Simplify the LULC
    p.lulc_simplifications_task = p.add_task(seals_generate_base_data.lulc_simplifications, parent=p.fine_processed_inputs_task, creates_dir=False)

    # Convert the simplified LULC into 1 binary presence map for each simplified LUC
    p.lulc_binaries_task = p.add_task(seals_generate_base_data.lulc_binaries, parent=p.fine_processed_inputs_task, creates_dir=False)

    # Convolve the lulc_binaries # TODOO Precache this for performance
    p.lulc_convolutions_task = p.add_task(seals_generate_base_data.lulc_convolutions, parent=p.fine_processed_inputs_task, creates_dir=False)

    # # Write a LOCAL version of the regression starting values based on the new data generated.
    # p.local_data_regression_starting_values_task = p.add_task(seals_generate_base_data.local_data_regressors_starting_values)


    ##### COARSE CHANGE #####
    # Make folder for all generated data.
    p.coarse_change_task = p.add_task(seals_process_coarse_timeseries.coarse_change, skip_existing=0)

    # Extract coarse change from source
    p.extraction_task = p.add_task(seals_process_coarse_timeseries.coarse_extraction, parent=p.coarse_change_task, run=1, skip_existing=0)

    # Reclassify coarse source to simplified scheme 
    p.coarse_simplified_task = p.add_task(seals_process_coarse_timeseries.coarse_simplified_proportion, parent=p.coarse_change_task, skip_existing=0)

    # Calculate LUH2_simplified difference from base year
    p.coarse_simplified_ha_difference_from_previous_year_task = p.add_task(seals_process_coarse_timeseries.coarse_simplified_ha_difference_from_previous_year, parent=p.coarse_change_task, skip_existing=0)


    ##### ALLOCATION #####

    # Iterate through different scenarios to be allocated.
    p.allocations_task = p.add_iterator(seals_main.allocations, run_in_parallel=0, skip_existing=0)

    # Define the zones overwhich parallel allocation should be run
    p.allocation_zones_task = p.add_iterator(seals_main.allocation_zones, parent=p.allocations_task, run_in_parallel=p.run_in_parallel, skip_existing=0)

    # Actually do the allocation
    p.allocation_task = p.add_task(seals_main.allocation, parent=p.allocation_zones_task, skip_existing=1)



    ##### STITCH ZONES #####

    # Stitch the simplified LULC tiles back together
    p.stitched_lulc_simplified_scenarios_task = p.add_task(seals_main.stitched_lulc_simplified_scenarios)

    # # Reclassify the stitched simplified to original classification.
    # p.stitched_lulc_esa_scenarios_task =  p.add_task(seals_main.stitched_lulc_esa_scenarios)

    # p.post_run_visualization_task = p.add_task(seals_visualization_tasks.post_run_visualization)

    ##### VIZUALIZE EXISTING DATA #####
    # Make folder for all visualizations.
    p.visualization_task = p.add_task(seals_visualization_tasks.visualization, skip_existing=0, run=1)

    # For each class, plot the coarse and fine data
    p.coarse_change_with_class_change_task = p.add_task(seals_visualization_tasks.coarse_change_with_class_change, parent=p.visualization_task, run=0)

    # For each class, plot the coarse and fine data
    p.create_full_change_matrices_task = p.add_task(seals_main.full_change_matrices, parent=p.visualization_task, run=0)
    
    # For each class, plot the coarse and fine data
    p.target_zones_matrices_task = p.add_task(seals_main.target_zones_matrices, parent=p.visualization_task, run=0)
    
    # For each class, plot the coarse and fine data
    p.plot_full_change_matrices_pngs_task = p.add_task(seals_visualization_tasks.full_change_matrices_pngs, parent=p.visualization_task, run=0)
    
    # For each class, plot the coarse and fine data
    p.plot_target_zones_matrices_pngs_task = p.add_task(seals_visualization_tasks.target_zones_matrices_pngs, parent=p.visualization_task, run=0)

    # Simple plot of the PNGs.
    p.lulc_pngs_task = p.add_task(seals_visualization_tasks.lulc_pngs, parent=p.visualization_task, run=1)
 


def build_standard_run_task_tree_BORK(p):

    # Define the project AOI
    p.project_aoi_task = p.add_task(project_aoi)

    # # Download the base data (note that it saves to p.base_data_dir and thus doesn't create its own dir)
    # p.base_data_task = p.add_task(seals_process_coarse_timeseries.download_base_data, creates_dir=False)


    ##### FINE PROCESSED INPUTS #####

    # Make folder for all generated data.
    p.fine_processed_inputs_task = p.add_task(seals_generate_base_data.fine_processed_inputs)

    # Generate some simple gaussian kernels for later convolutions
    p.generated_kernels_task = p.add_task(seals_generate_base_data.generated_kernels, parent=p.fine_processed_inputs_task, creates_dir=False)

    # Clip the fine LULC to the project AOI
    p.lulc_clip_task = p.add_task(seals_generate_base_data.lulc_clip, parent=p.fine_processed_inputs_task, creates_dir=False)

    # Simplify the LULC
    p.lulc_simplifications_task = p.add_task(seals_generate_base_data.lulc_simplifications, parent=p.fine_processed_inputs_task, creates_dir=False)

    # Convert the simplified LULC into 1 binary presence map for each simplified LUC
    p.lulc_binaries_task = p.add_task(seals_generate_base_data.lulc_binaries, parent=p.fine_processed_inputs_task, creates_dir=False)

    # Convolve the lulc_binaries # TODOO Precache this for performance
    p.lulc_convolutions_task = p.add_task(seals_generate_base_data.lulc_convolutions, parent=p.fine_processed_inputs_task, creates_dir=False)

    # # Write a LOCAL version of the regression starting values based on the new data generated.
    # p.local_data_regression_starting_values_task = p.add_task(seals_generate_base_data.local_data_regressors_starting_values)


    ##### COARSE CHANGE #####
    # Make folder for all generated data.
    p.coarse_change_task = p.add_task(seals_process_coarse_timeseries.coarse_change, skip_existing=0)

    # Extract coarse change from source
    p.extraction_task = p.add_task(seals_process_coarse_timeseries.coarse_extraction, parent=p.coarse_change_task, run=1, skip_existing=0)

    # Reclassify coarse source to simplified scheme 
    p.coarse_simplified_task = p.add_task(seals_process_coarse_timeseries.coarse_simplified_proportion, parent=p.coarse_change_task, skip_existing=0)

    # Calculate LUH2_simplified difference from base year
    p.coarse_simplified_ha_difference_from_previous_year_task = p.add_task(seals_process_coarse_timeseries.coarse_simplified_ha_difference_from_previous_year, parent=p.coarse_change_task, skip_existing=0)


    ##### ALLOCATION #####

    # Iterate through different scenarios to be allocated.
    p.allocations_task = p.add_iterator(seals_main.allocations)

    # Define the zones overwhich parallel allocation should be run
    p.allocation_zones_task = p.add_iterator(seals_main.allocation_zones, parent=p.allocations_task)

    # Actually do the allocation
    p.allocation_task = p.add_task(seals_main.allocation, parent=p.allocation_zones_task, skip_existing=1)



    ##### STITCH ZONES #####

    # Stitch the simplified LULC tiles back together
    p.stitched_lulc_simplified_scenarios_task = p.add_task(seals_main.stitched_lulc_simplified_scenarios)

    # # Reclassify the stitched simplified to original classification.
    # p.stitched_lulc_esa_scenarios_task =  p.add_task(seals_main.stitched_lulc_esa_scenarios)

    # p.post_run_visualization_task = p.add_task(seals_visualization_tasks.post_run_visualization)

    ##### VIZUALIZE EXISTING DATA #####
    # Make folder for all visualizations.
    p.visualization_task = p.add_task(seals_visualization_tasks.visualization, skip_existing=0, run=1)

    # For each class, plot the coarse and fine data
    p.coarse_change_with_class_change_task = p.add_task(seals_visualization_tasks.coarse_change_with_class_change, parent=p.visualization_task, run=0)

    # For each class, plot the coarse and fine data
    p.plot_full_change_matrices_task = p.add_task(seals_main.full_change_matrices, parent=p.visualization_task, run=0)
    
    # For each class, plot the coarse and fine data
    p.plot_full_change_matrices_task = p.add_task(seals_visualization_tasks.full_change_matrices_pngs, parent=p.visualization_task, run=0)

    # Simple plot of the PNGs.
    p.lulc_pngs_task = p.add_task(seals_visualization_tasks.lulc_pngs, parent=p.visualization_task, run=1)

    p.coarse_fine_with_report_task = p.add_task(seals_visualization_tasks.coarse_fine_with_report, parent=p.visualization_task, run=0)


def build_standard_run_task_tree(p):

    # Define the project AOI
    p.project_aoi_task = p.add_task(seals_tasks.project_aoi)

    ##### FINE PROCESSED INPUTS #####    
    p.fine_processed_inputs_task = p.add_task(seals_generate_base_data.fine_processed_inputs)
    p.generated_kernels_task = p.add_task(seals_generate_base_data.generated_kernels, parent=p.fine_processed_inputs_task, creates_dir=False)
    p.lulc_clip_task = p.add_task(seals_generate_base_data.lulc_clip, parent=p.fine_processed_inputs_task, creates_dir=False)
    p.lulc_simplifications_task = p.add_task(seals_generate_base_data.lulc_simplifications, parent=p.fine_processed_inputs_task, creates_dir=False)
    p.lulc_binaries_task = p.add_task(seals_generate_base_data.lulc_binaries, parent=p.fine_processed_inputs_task, creates_dir=False)
    p.lulc_convolutions_task = p.add_task(seals_generate_base_data.lulc_convolutions, parent=p.fine_processed_inputs_task, creates_dir=False)

    ##### COARSE CHANGE #####
    p.coarse_change_task = p.add_task(seals_process_coarse_timeseries.coarse_change, skip_existing=0)
    p.extraction_task = p.add_task(seals_process_coarse_timeseries.coarse_extraction, parent=p.coarse_change_task, run=1, skip_existing=0)
    p.coarse_simplified_task = p.add_task(seals_process_coarse_timeseries.coarse_simplified_proportion, parent=p.coarse_change_task, skip_existing=0)
    p.coarse_simplified_ha_task = p.add_task(seals_process_coarse_timeseries.coarse_simplified_ha, parent=p.coarse_change_task, skip_existing=0)
    p.coarse_simplified_ha_difference_from_previous_year_task = p.add_task(seals_process_coarse_timeseries.coarse_simplified_ha_difference_from_previous_year, parent=p.coarse_change_task, skip_existing=0)

    ##### REGIONAL 
    p.regional_change_task = p.add_task(seals_process_coarse_timeseries.regional_change)     

    ##### ALLOCATION #####
    p.allocations_task = p.add_iterator(seals_main.allocations)
    p.allocation_zones_task = p.add_iterator(seals_main.allocation_zones, run_in_parallel=p.run_in_parallel, parent=p.allocations_task)
    p.allocation_task = p.add_task(seals_main.allocation, parent=p.allocation_zones_task, skip_existing=1)

    ##### STITCH ZONES #####
    p.stitched_lulc_simplified_scenarios_task = p.add_task(seals_main.stitched_lulc_simplified_scenarios)

    ##### VIZUALIZE EXISTING DATA #####
    p.visualization_task = p.add_task(seals_visualization_tasks.visualization)
    p.lulc_pngs_task = p.add_task(seals_visualization_tasks.lulc_pngs, parent=p.visualization_task)
    
    


def build_complete_run_task_tree(p):
    ## OUT OF DATE, but should be replicated
    p.project_aoi_task = p.add_task(project_aoi)
    p.base_data_task = p.add_task(seals_process_coarse_timeseries.download_base_data, creates_dir=False,                                                         run=1, skip_existing=0)
    p.regressors_starting_values_task = p.add_task(seals_generate_base_data.regressors_starting_values,                                             run=1, skip_existing=0)
    p.generated_data_task = p.add_task(seals_generate_base_data.generated_data,                                                                     run=1, skip_existing=0)
    p.aoi_vector_task = p.add_task(seals_generate_base_data.aoi_vector, parent=p.generated_data_task, creates_dir=False,                            run=1, skip_existing=0)
    p.lulc_clip_task = p.add_task(seals_generate_base_data.lulc_clip, parent=p.generated_data_task, creates_dir=False,                              run=1, skip_existing=0)
    p.lulc_simplifications_task = p.add_task(seals_generate_base_data.lulc_simplifications, parent=p.generated_data_task, creates_dir=False,        run=1, skip_existing=0)
    p.lulc_binaries_task = p.add_task(seals_generate_base_data.lulc_binaries, parent=p.generated_data_task, creates_dir=False,                      run=1, skip_existing=0)
    p.generated_kernels_task = p.add_task(seals_generate_base_data.generated_kernels, parent=p.generated_data_task, creates_dir=False,              run=1, skip_existing=0)
    p.lulc_convolutions_task = p.add_task(seals_generate_base_data.lulc_convolutions, parent=p.generated_data_task, creates_dir=False,              run=1, skip_existing=0)
    p.local_data_regression_starting_values_task = p.add_task(seals_generate_base_data.local_data_regressors_starting_values,                       run=1, skip_existing=0)
    p.luh2_extraction_task = p.add_task(seals_process_coarse_timeseries.luh2_extraction,                                                                         run=1, skip_existing=0)
    p.luh2_difference_from_base_year_task = p.add_task(seals_process_coarse_timeseries.luh2_difference_from_base_year,                                           run=1, skip_existing=0)
    p.luh2_as_simplified_proportion_task = p.add_task(seals_process_coarse_timeseries.luh2_as_simplified_proportion,                                                     run=1, skip_existing=0)
    p.simplified_difference_from_base_yea_task = p.add_task(seals_process_coarse_timeseries.simplified_difference_from_base_year,                                        run=1, skip_existing=0)
    p.calibration_generated_inputs_task = p.add_task(seals_main.calibration_generated_inputs,                                                       run=1, skip_existing=0)
    p.calibration_task = p.add_iterator(seals_main.calibration, run_in_parallel=1,                                                                  run=1, skip_existing=0)
    p.calibration_prepare_lulc_task = p.add_task(seals_main.calibration_prepare_lulc, parent=p.calibration_task,                                    run=1, skip_existing=0)
    p.calibration_change_matrix_task = p.add_task(seals_main.calibration_change_matrix, parent=p.calibration_task,                                  run=1, skip_existing=0)
    p.calibration_zones_task = p.add_task(seals_main.calibration_zones, parent=p.calibration_task,                                                  run=1, skip_existing=0, logging_level=20)
    p.calibration_plots_task = p.add_task(seals_main.calibration_plots, parent=p.calibration_task,                                                  run=1, skip_existing=0)
    p.combined_trained_coefficients_task = p.add_task(seals_main.combined_trained_coefficients,                                                     run=1, skip_existing=0)
    p.allocations_task = p.add_iterator(seals_main.allocations, run_in_parallel=0,                                                                  run=1, skip_existing=0)
    p.allocation_zones_task = p.add_iterator(seals_main.allocation_zones, parent=p.allocations_task, run_in_parallel=1,                             run=1, skip_existing=0)
    p.allocation_change_matrix_task = p.add_task(seals_main.allocation_change_matrix, parent=p.allocation_zones_task,                               run=1, skip_existing=0)
    p.allocation_task = p.add_task(seals_main.allocation, parent=p.allocation_zones_task,                                                           run=1, skip_existing=0)
    p.allocation_exclusive_task = p.add_task(seals_main.allocation_exclusive, parent=p.allocation_zones_task,                                       run=0, skip_existing=0)
    p.allocation_from_change_matrix_task = p.add_task(seals_main.allocation_from_change_matrix, parent=p.allocation_zones_task,                     run=0, skip_existing=0)
    p.change_pngs_task = p.add_task(seals_main.change_pngs, parent=p.allocation_zones_task,                                                         run=0, skip_existing=0)
    p.change_exclusive_pngs_task = p.add_task(seals_main.change_exclusive_pngs, parent=p.allocation_zones_task,                                     run=0, skip_existing=0)
    p.change_from_change_matrix_pngs_task = p.add_task(seals_main.change_from_change_matrix_pngs, parent=p.allocation_zones_task,                   run=0, skip_existing=0)
    p.stitched_lulc_simplified_scenarios_task = p.add_task(seals_main.stitched_lulc_simplified_scenarios,                                           run=1, skip_existing=0)
    p.stitched_lulc_esa_scenarios_task =  p.add_task(seals_main.stitched_lulc_esa_scenarios,                                                        run=1, skip_existing=0)

    return p


def build_global_carbon_by_scenario_task_tree(p):
    # Example of a post-run task tree
    p.project_aoi_task = p.add_task(project_aoi)
    # NOTE. Because p.stitched_lulc_esa_scenarios_dir is referenced in carbon_comparison, need to call but not run the corresponding task.
    p.simplified_difference_from_base_year_task =  p.add_task(seals_process_coarse_timeseries.simplified_difference_from_base_year,                 run=0, skip_existing=0)
    p.stitched_lulc_esa_scenarios_task =  p.add_task(seals_main.stitched_lulc_esa_scenarios,                                                        run=0, skip_existing=0)
    p.stitched_lulc_simplified_scenarios_task =  p.add_task(seals_main.stitched_lulc_simplified_scenarios,                                          run=0, skip_existing=0)
    p.global_carbon_by_scenario_task = p.add_task(seals_main.global_carbon_by_scenario,                                                             run=1, skip_existing=0)
    p.carbon_comparison_task = p.add_task(seals_main.carbon_comparison,                                                                             run=1, skip_existing=0)




def build_iucn_30by30_task_tree(p):
    
    # DEPRACATED FOR BUILD_IUCN_TASK_TREE()

    # Define the project AOI
    p.project_aoi_task = p.add_task(project_aoi)
    
    # Process the IUCN-specific data to be used in SEALS
    p.biodiversity_task = p.add_task(seals_generate_base_data.biodiversity)
    p.kbas_task = p.add_task(seals_generate_base_data.kba, parent=p.biodiversity_task)
    p.star_task = p.add_task(seals_generate_base_data.star, parent=p.biodiversity_task)
    

    ##### FINE PROCESSED INPUTS #####    
    p.fine_processed_inputs_task = p.add_task(seals_generate_base_data.fine_processed_inputs)
    p.generated_kernels_task = p.add_task(seals_generate_base_data.generated_kernels, parent=p.fine_processed_inputs_task, creates_dir=False)
    p.lulc_clip_task = p.add_task(seals_generate_base_data.lulc_clip, parent=p.fine_processed_inputs_task, creates_dir=False)
    p.lulc_simplifications_task = p.add_task(seals_generate_base_data.lulc_simplifications, parent=p.fine_processed_inputs_task, creates_dir=False)
    p.lulc_binaries_task = p.add_task(seals_generate_base_data.lulc_binaries, parent=p.fine_processed_inputs_task, creates_dir=False)
    p.lulc_convolutions_task = p.add_task(seals_generate_base_data.lulc_convolutions, parent=p.fine_processed_inputs_task, creates_dir=False)

    ##### COARSE CHANGE #####
    p.coarse_change_task = p.add_task(seals_process_coarse_timeseries.coarse_change, skip_existing=0)
    p.extraction_task = p.add_task(seals_process_coarse_timeseries.coarse_extraction, parent=p.coarse_change_task, run=1, skip_existing=0)
    p.coarse_simplified_task = p.add_task(seals_process_coarse_timeseries.coarse_simplified_proportion, parent=p.coarse_change_task, skip_existing=0)
    p.coarse_simplified_ha_task = p.add_task(seals_process_coarse_timeseries.coarse_simplified_ha, parent=p.coarse_change_task, skip_existing=0)
    p.coarse_simplified_ha_difference_from_previous_year_task = p.add_task(seals_process_coarse_timeseries.coarse_simplified_ha_difference_from_previous_year, parent=p.coarse_change_task, skip_existing=0)


    # IUCN SPECIFIC
    p.iucn_30by30_scenarios_task = p.add_task(seals_main.iucn_30by30_scenarios)     
    p.protection_by_aezreg_to_meet_30by30_task = p.add_task(seals_main.protection_by_aezreg_to_meet_30by30, parent=p.iucn_30by30_scenarios_task)
    p.ag_value_task = p.add_task(seals_main.ag_value, parent=p.iucn_30by30_scenarios_task)
    

    # Make a new coarse resolution projection based on a vector
    p.luh_seals_baseline_adjustment_task = p.add_task(seals_main.luh_seals_baseline_adjustment, parent=p.coarse_change_task)
    p.coarse_simplified_projected_ha_difference_from_previous_year_task = p.add_task(seals_main.coarse_simplified_projected_ha_difference_from_previous_year)
    p.vector_projections_to_coarse_raster_task = p.add_task(seals_main.vector_projections_to_coarse_raster)
    

    ##### ALLOCATION #####
    p.allocations_task = p.add_iterator(seals_main.allocations)
    p.allocation_zones_task = p.add_iterator(seals_main.allocation_zones, run_in_parallel=p.run_in_parallel, parent=p.allocations_task)
    p.allocation_task = p.add_task(seals_main.allocation, parent=p.allocation_zones_task, skip_existing=1)

    ##### STITCH ZONES #####
    p.stitched_lulc_simplified_scenarios_task = p.add_task(seals_main.stitched_lulc_simplified_scenarios)

    ##### VIZUALIZE EXISTING DATA #####
    p.visualization_task = p.add_task(seals_visualization_tasks.visualization, skip_existing=0, run=1)
    p.coarse_change_with_class_change_task = p.add_task(seals_visualization_tasks.coarse_change_with_class_change, parent=p.visualization_task, run=0)
    p.plot_full_change_matrices_task = p.add_task(seals_main.full_change_matrices, parent=p.visualization_task, run=0)
    p.plot_full_change_matrices_task = p.add_task(seals_visualization_tasks.full_change_matrices_pngs, parent=p.visualization_task, run=0)
    p.lulc_pngs_task = p.add_task(seals_visualization_tasks.lulc_pngs, parent=p.visualization_task, run=1)
    p.coarse_fine_with_report_task = p.add_task(seals_visualization_tasks.coarse_fine_with_report, parent=p.visualization_task, run=0)


def build_iucn_task_tree(p):

    # Define the project AOI
    p.project_aoi_task = p.add_task(project_aoi)
    
    # Process the IUCN-specific data to be used in SEALS
    p.biodiversity_task = p.add_task(seals_generate_base_data.biodiversity)
    p.kbas_task = p.add_task(seals_generate_base_data.kba, parent=p.biodiversity_task)
    p.star_task = p.add_task(seals_generate_base_data.star, parent=p.biodiversity_task)

    ##### FINE PROCESSED INPUTS #####    
    p.fine_processed_inputs_task = p.add_task(seals_generate_base_data.fine_processed_inputs)
    p.generated_kernels_task = p.add_task(seals_generate_base_data.generated_kernels, parent=p.fine_processed_inputs_task, creates_dir=False)
    p.lulc_clip_task = p.add_task(seals_generate_base_data.lulc_clip, parent=p.fine_processed_inputs_task, creates_dir=False)
    p.lulc_simplifications_task = p.add_task(seals_generate_base_data.lulc_simplifications, parent=p.fine_processed_inputs_task, creates_dir=False)
    p.lulc_binaries_task = p.add_task(seals_generate_base_data.lulc_binaries, parent=p.fine_processed_inputs_task, creates_dir=False)
    p.lulc_convolutions_task = p.add_task(seals_generate_base_data.lulc_convolutions, parent=p.fine_processed_inputs_task, creates_dir=False)

    ##### COARSE CHANGE #####
    p.coarse_change_task = p.add_task(seals_process_coarse_timeseries.coarse_change, skip_existing=0)
    p.extraction_task = p.add_task(seals_process_coarse_timeseries.coarse_extraction, parent=p.coarse_change_task, run=1, skip_existing=0)
    p.coarse_simplified_task = p.add_task(seals_process_coarse_timeseries.coarse_simplified_proportion, parent=p.coarse_change_task, skip_existing=0)
    p.coarse_simplified_ha_task = p.add_task(seals_process_coarse_timeseries.coarse_simplified_ha, parent=p.coarse_change_task, skip_existing=0)
    p.coarse_simplified_ha_difference_from_previous_year_task = p.add_task(seals_process_coarse_timeseries.coarse_simplified_ha_difference_from_previous_year, parent=p.coarse_change_task, skip_existing=0)

    # IUCN SPECIFIC
    p.iucn_30by30_scenarios_task = p.add_task(seals_main.iucn_30by30_scenarios)     
    p.protection_by_aezreg_to_meet_30by30_task = p.add_task(seals_main.protection_by_aezreg_to_meet_30by30, parent=p.iucn_30by30_scenarios_task)
    p.ag_value_task = p.add_task(seals_main.ag_value, parent=p.iucn_30by30_scenarios_task)
    p.luh_seals_baseline_adjustment_task = p.add_task(seals_main.luh_seals_baseline_adjustment, parent=p.iucn_30by30_scenarios_task)
    p.coarse_simplified_projected_ha_difference_from_previous_year_task = p.add_task(seals_main.coarse_simplified_projected_ha_difference_from_previous_year, parent=p.iucn_30by30_scenarios_task)


    ##### ALLOCATION #####
    p.allocations_task = p.add_iterator(seals_main.allocations)
    p.allocation_zones_task = p.add_iterator(seals_main.allocation_zones, run_in_parallel=p.run_in_parallel, parent=p.allocations_task)
    p.allocation_task = p.add_task(seals_main.allocation, parent=p.allocation_zones_task, skip_existing=1)

    ##### STITCH ZONES #####
    p.stitched_lulc_simplified_scenarios_task = p.add_task(seals_main.stitched_lulc_simplified_scenarios)



def build_regional_coarse_fine_allocation_task_tree(p):

    # Define the project AOI
    p.project_aoi_task = p.add_task(project_aoi)
    
    # Process the IUCN-specific data to be used in SEALS
    p.biodiversity_task = p.add_task(seals_generate_base_data.biodiversity)
    p.kbas_task = p.add_task(seals_generate_base_data.kba, parent=p.biodiversity_task)
    p.star_task = p.add_task(seals_generate_base_data.star, parent=p.biodiversity_task)

    ##### FINE PROCESSED INPUTS #####    
    p.fine_processed_inputs_task = p.add_task(seals_generate_base_data.fine_processed_inputs)
    p.generated_kernels_task = p.add_task(seals_generate_base_data.generated_kernels, parent=p.fine_processed_inputs_task, creates_dir=False)
    p.lulc_clip_task = p.add_task(seals_generate_base_data.lulc_clip, parent=p.fine_processed_inputs_task, creates_dir=False)
    p.lulc_simplifications_task = p.add_task(seals_generate_base_data.lulc_simplifications, parent=p.fine_processed_inputs_task, creates_dir=False)
    p.lulc_binaries_task = p.add_task(seals_generate_base_data.lulc_binaries, parent=p.fine_processed_inputs_task, creates_dir=False)
    p.lulc_convolutions_task = p.add_task(seals_generate_base_data.lulc_convolutions, parent=p.fine_processed_inputs_task, creates_dir=False)

    ##### COARSE CHANGE #####
    p.coarse_change_task = p.add_task(seals_process_coarse_timeseries.coarse_change, skip_existing=0)
    p.extraction_task = p.add_task(seals_process_coarse_timeseries.coarse_extraction, parent=p.coarse_change_task, run=1, skip_existing=0)
    p.coarse_simplified_task = p.add_task(seals_process_coarse_timeseries.coarse_simplified_proportion, parent=p.coarse_change_task, skip_existing=0)
    p.coarse_simplified_ha_task = p.add_task(seals_process_coarse_timeseries.coarse_simplified_ha, parent=p.coarse_change_task, skip_existing=0)
    p.coarse_simplified_ha_difference_from_previous_year_task = p.add_task(seals_process_coarse_timeseries.coarse_simplified_ha_difference_from_previous_year, parent=p.coarse_change_task, skip_existing=0)

    # IUCN SPECIFIC
    p.restoration_task = p.add_task(seals_main.restoration)     
    p.protection_by_aezreg_to_meet_30by30_task = p.add_task(seals_main.protection_by_aezreg_to_meet_30by30, parent=p.restoration_task)
    p.ag_value_task = p.add_task(seals_main.ag_value, parent=p.restoration_task)
    p.luh_seals_baseline_adjustment_task = p.add_task(seals_main.luh_seals_baseline_adjustment, parent=p.restoration_task)
    p.coarse_simplified_projected_ha_difference_from_previous_year_task = p.add_task(seals_main.coarse_simplified_projected_ha_difference_from_previous_year, parent=p.iucn_30by30_scenarios_task)


    ##### ALLOCATION #####
    p.allocations_task = p.add_iterator(seals_main.allocations)
    p.allocation_zones_task = p.add_iterator(seals_main.allocation_zones, run_in_parallel=p.run_in_parallel, parent=p.allocations_task)
    p.allocation_task = p.add_task(seals_main.allocation, parent=p.allocation_zones_task, skip_existing=1)

    ##### STITCH ZONES #####
    p.stitched_lulc_simplified_scenarios_task = p.add_task(seals_main.stitched_lulc_simplified_scenarios)

    ##### VIZUALIZE EXISTING DATA #####
    p.visualization_task = p.add_task(seals_visualization_tasks.visualization)
    # p.coarse_change_with_class_change_task = p.add_task(seals_visualization_tasks.coarse_change_with_class_change, parent=p.visualization_task)
    # p.plot_full_change_matrices_task = p.add_task(seals_main.full_change_matrices, parent=p.visualization_task)
    # p.plot_full_change_matrices_task = p.add_task(seals_visualization_tasks.full_change_matrices_pngs, parent=p.visualization_task)
    p.lulc_pngs_task = p.add_task(seals_visualization_tasks.lulc_pngs, parent=p.visualization_task)
    # p.coarse_fine_with_report_task = p.add_task(seals_visualization_tasks.coarse_fine_with_report, parent=p.visualization_task)
    
    
    # For each class, plot the coarse and fine data
    # p.create_full_change_matrices_task = p.add_task(seals_main.full_change_matrices, parent=p.visualization_task)
    
    # For each class, plot the coarse and fine data
    # p.target_zones_matrices_task = p.add_task(seals_main.target_zones_matrices, parent=p.visualization_task)
    
    # For each class, plot the coarse and fine data
    # p.plot_full_change_matrices_pngs_task = p.add_task(seals_visualization_tasks.full_change_matrices_pngs, parent=p.visualization_task)
    
    # For each class, plot the coarse and fine data
    # p.plot_target_zones_matrices_pngs_task = p.add_task(seals_visualization_tasks.target_zones_matrices_pngs, parent=p.visualization_task)




def build_regional_coarse_fine_restoration_shift_task_tree(p):

    # Define the project AOI
    p.project_aoi_task = p.add_task(project_aoi)

    ##### FINE PROCESSED INPUTS #####    
    p.fine_processed_inputs_task = p.add_task(seals_generate_base_data.fine_processed_inputs)
    p.generated_kernels_task = p.add_task(seals_generate_base_data.generated_kernels, parent=p.fine_processed_inputs_task, creates_dir=False)
    p.lulc_clip_task = p.add_task(seals_generate_base_data.lulc_clip, parent=p.fine_processed_inputs_task, creates_dir=False)
    p.lulc_simplifications_task = p.add_task(seals_generate_base_data.lulc_simplifications, parent=p.fine_processed_inputs_task, creates_dir=False)
    p.lulc_binaries_task = p.add_task(seals_generate_base_data.lulc_binaries, parent=p.fine_processed_inputs_task, creates_dir=False)
    p.lulc_convolutions_task = p.add_task(seals_generate_base_data.lulc_convolutions, parent=p.fine_processed_inputs_task, creates_dir=False)

    ##### COARSE CHANGE #####
    p.coarse_change_task = p.add_task(seals_process_coarse_timeseries.coarse_change, skip_existing=0)
    p.extraction_task = p.add_task(seals_process_coarse_timeseries.coarse_extraction, parent=p.coarse_change_task, run=1, skip_existing=0)
    p.coarse_simplified_task = p.add_task(seals_process_coarse_timeseries.coarse_simplified_proportion, parent=p.coarse_change_task, skip_existing=0)
    p.coarse_simplified_ha_task = p.add_task(seals_process_coarse_timeseries.coarse_simplified_ha, parent=p.coarse_change_task, skip_existing=0)
    p.coarse_simplified_ha_difference_from_previous_year_task = p.add_task(seals_process_coarse_timeseries.coarse_simplified_ha_difference_from_previous_year, parent=p.coarse_change_task, skip_existing=0)

    # IUCN SPECIFIC
    p.restoration_task = p.add_task(seals_main.restoration)     
    p.protection_by_aezreg_to_meet_30by30_task = p.add_task(seals_main.protection_by_aezreg_to_meet_30by30, parent=p.restoration_task)
    p.luh_seals_baseline_adjustment_task = p.add_task(seals_main.luh_seals_baseline_adjustment, parent=p.restoration_task)
    p.coarse_simplified_projected_ha_difference_from_previous_year_task = p.add_task(seals_main.coarse_simplified_projected_ha_difference_from_previous_year, parent=p.restoration_task)


    ##### ALLOCATION #####
    p.allocations_task = p.add_iterator(seals_main.allocations)
    p.allocation_zones_task = p.add_iterator(seals_main.allocation_zones, run_in_parallel=p.run_in_parallel, parent=p.allocations_task)
    p.allocation_task = p.add_task(seals_main.allocation, parent=p.allocation_zones_task, skip_existing=1)

    ##### STITCH ZONES #####
    p.stitched_lulc_simplified_scenarios_task = p.add_task(seals_main.stitched_lulc_simplified_scenarios)

    ##### VIZUALIZE EXISTING DATA #####
    p.visualization_task = p.add_task(seals_visualization_tasks.visualization)
    p.lulc_pngs_task = p.add_task(seals_visualization_tasks.lulc_pngs, parent=p.visualization_task)


def build_regional_coarse_fine_manual_shift_task_tree(p):

    # Define the project AOI
    p.project_aoi_task = p.add_task(project_aoi)

    ##### FINE PROCESSED INPUTS #####    
    p.fine_processed_inputs_task = p.add_task(seals_generate_base_data.fine_processed_inputs)
    p.generated_kernels_task = p.add_task(seals_generate_base_data.generated_kernels, parent=p.fine_processed_inputs_task, creates_dir=False)
    p.lulc_clip_task = p.add_task(seals_generate_base_data.lulc_clip, parent=p.fine_processed_inputs_task, creates_dir=False)
    p.lulc_simplifications_task = p.add_task(seals_generate_base_data.lulc_simplifications, parent=p.fine_processed_inputs_task, creates_dir=False)
    p.lulc_binaries_task = p.add_task(seals_generate_base_data.lulc_binaries, parent=p.fine_processed_inputs_task, creates_dir=False)
    p.lulc_convolutions_task = p.add_task(seals_generate_base_data.lulc_convolutions, parent=p.fine_processed_inputs_task, creates_dir=False)

    ##### COARSE CHANGE #####
    p.coarse_change_task = p.add_task(seals_process_coarse_timeseries.coarse_change, skip_existing=0)
    p.extraction_task = p.add_task(seals_process_coarse_timeseries.coarse_extraction, parent=p.coarse_change_task, run=1, skip_existing=0)
    p.coarse_simplified_task = p.add_task(seals_process_coarse_timeseries.coarse_simplified_proportion, parent=p.coarse_change_task, skip_existing=0)
    p.coarse_simplified_ha_task = p.add_task(seals_process_coarse_timeseries.coarse_simplified_ha, parent=p.coarse_change_task, skip_existing=0)
    p.coarse_simplified_ha_difference_from_previous_year_task = p.add_task(seals_process_coarse_timeseries.coarse_simplified_ha_difference_from_previous_year, parent=p.coarse_change_task, skip_existing=0)

    ##### REGIONAL 
    p.regional_change_task = p.add_task(seals_process_coarse_timeseries.regional_change)     


    ##### ALLOCATION #####
    p.allocations_task = p.add_iterator(seals_main.allocations)
    p.allocation_zones_task = p.add_iterator(seals_main.allocation_zones, run_in_parallel=p.run_in_parallel, parent=p.allocations_task)
    p.allocation_task = p.add_task(seals_main.allocation, parent=p.allocation_zones_task, skip_existing=1)

    ##### STITCH ZONES #####
    p.stitched_lulc_simplified_scenarios_task = p.add_task(seals_main.stitched_lulc_simplified_scenarios)

    ##### VIZUALIZE EXISTING DATA #####
    p.visualization_task = p.add_task(seals_visualization_tasks.visualization)
    p.lulc_pngs_task = p.add_task(seals_visualization_tasks.lulc_pngs, parent=p.visualization_task)
    
    
