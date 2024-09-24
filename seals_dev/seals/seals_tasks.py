import os
import hazelbean as hb


def project_aoi(p):

    p.ha_per_cell_coarse_path = p.get_path(hb.ha_per_cell_ref_paths[p.coarse_resolution_arcseconds])
    p.ha_per_cell_fine_path = p.get_path(hb.ha_per_cell_ref_paths[p.fine_resolution_arcseconds])
    
    # Process p.aoi to set the regional_vector, bb, bb_exact, and aoi_ha_per_cell_paths
    if isinstance(p.aoi, str):
        if p.aoi == 'global':
            p.aoi_path = p.global_regions_vector_path
            p.aoi_label = 'global'
            p.bb_exact = hb.global_bounding_box
            p.bb = p.bb_exact

            p.aoi_ha_per_cell_coarse_path = p.ha_per_cell_coarse_path
            p.aoi_ha_per_cell_fine_path = p.ha_per_cell_fine_path
        
        elif isinstance(p.aoi, str):
            if len(p.aoi) == 3: # Then it might be an ISO3 code. For now, assume so.
                p.aoi_path = os.path.join(p.cur_dir, 'aoi_' + str(p.aoi) + '.gpkg')
                p.aoi_label = p.aoi
            else: # Then it's a path to a shapefile.
                p.aoi_path = p.aoi
                p.aoi_label = os.path.splitext(os.path.basename(p.aoi))[0]

            for current_aoi_path in hb.list_filtered_paths_nonrecursively(p.cur_dir, include_strings='aoi'):
                if current_aoi_path != p.aoi_path:
                    raise NameError('There is more than one AOI in the current directory. This means you are trying to run a project in a new area of interst in a project that was already run in a different area of interest. This is not allowed! You probably want to create a new project directory and set the p = hb.ProjectFlow(...) line to point to the new directory.')

            if not hb.path_exists(p.aoi_path):
                hb.extract_features_in_shapefile_by_attribute(p.global_regions_vector_path, p.aoi_path, 'ee_r264_label', p.aoi.upper())
            
            p.bb_exact = hb.spatial_projection.get_bounding_box(p.aoi_path)
            p.bb = hb.pyramids.get_pyramid_compatible_bb_from_vector_and_resolution(p.aoi_path, p.processing_resolution_arcseconds)
            
            
            # Create a PROJECT-SPECIFIC version of these clipped ones.
            p.aoi_ha_per_cell_fine_path = os.path.join(p.cur_dir, 'pyramids', 'aoi_ha_per_cell_fine.tif')
            if not hb.path_exists(p.aoi_ha_per_cell_fine_path):
                hb.create_directories(p.aoi_ha_per_cell_fine_path)
                
                #  make ha_per_cell_paths not be a dict but a project level ha_per_cell_fine_path etc
                hb.clip_raster_by_bb(p.ha_per_cell_fine_path, p.bb, p.aoi_ha_per_cell_fine_path)
            
            p.aoi_ha_per_cell_coarse_path = os.path.join(p.cur_dir, 'pyramids', 'aoi_ha_per_cell_coarse.tif')
            if not hb.path_exists(p.aoi_ha_per_cell_coarse_path):
                hb.create_directories(p.aoi_ha_per_cell_coarse_path)
                hb.clip_raster_by_bb(p.ha_per_cell_coarse_path, p.bb, p.aoi_ha_per_cell_coarse_path)
        
            
            
        else:
            p.bb_exact = hb.spatial_projection.get_bounding_box(p.aoi_path)
            p.bb = hb.pyramids.get_pyramid_compatible_bb_from_vector_and_resolution(p.aoi_path, p.processing_resolution_arcseconds)

            # Create a PROJECT-SPECIFIC version of these clipped ones.
            p.aoi_ha_per_cell_fine_path = os.path.join(p.cur_dir, 'pyramids', 'aoi_ha_per_cell_fine.tif')
            if not hb.path_exists(p.aoi_ha_per_cell_fine_path):
                hb.create_directories(p.aoi_ha_per_cell_fine_path)
                hb.clip_raster_by_bb(p.ha_per_cell_paths[p.fine_resolution_arcseconds], p.bb, p.aoi_ha_per_cell_fine_path)
            
            p.aoi_ha_per_cell_coarse_path = os.path.join(p.cur_dir, 'pyramids', 'aoi_ha_per_cell_coarse.tif')
            if not hb.path_exists(p.aoi_ha_per_cell_coarse_path):
                hb.create_directories(p.aoi_ha_per_cell_coarse_path)
                hb.clip_raster_by_bb(p.ha_per_cell_paths[p.coarse_resolution_arcseconds], p.bb, p.aoi_ha_per_cell_coarse_path)
                    
    else:
        raise NameError('Unable to interpret p.aoi.')
